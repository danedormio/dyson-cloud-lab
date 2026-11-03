"""Read-only checkout evidence for bounded development runs; not remote attestation."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit


def github_identity(remote):
    """Return only a normalized GitHub owner/repository, never remote credentials."""
    if remote.startswith('git@github.com:'):
        path = remote[len('git@github.com:'):]
    else:
        parsed = urlsplit(remote)
        if parsed.scheme not in ('https', 'ssh') or parsed.hostname != 'github.com':
            return None
        path = parsed.path.lstrip('/')
    if path.endswith('.git'):
        path = path[:-4]
    return path.lower() if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', path) else None


def inspect_checkout(directory, expected_sha, expected_repo):
    result = {'ok': False, 'head': None, 'repository': None, 'clean': None, 'errors': []}
    if not re.fullmatch(r'[0-9a-fA-F]{40}', expected_sha):
        result['errors'].append('expected_sha_must_be_full_40_hex')
        return result
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', expected_repo):
        result['errors'].append('invalid_expected_repository')
        return result
    # Disable optional index writes; do not print Git stderr or credential-bearing remotes.
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')

    def git(*args):
        return subprocess.run(['git', '-C', str(directory), *args], env=env,
                              capture_output=True, check=True, timeout=10).stdout.decode().strip()

    try:
        if git('rev-parse', '--is-inside-work-tree') != 'true':
            raise ValueError('not a worktree')
        # A nested folder could hide changes outside the selected project; inspect its root.
        root = Path(git('rev-parse', '--show-toplevel'))
        result['head'] = git('rev-parse', 'HEAD')
        result['repository'] = github_identity(git('remote', 'get-url', 'origin'))
        status = subprocess.run(['git', '-C', str(root), 'status', '--porcelain=v1',
                                 '--untracked-files=all', '--ignore-submodules=none'],
                                env=env, capture_output=True, check=True, timeout=10)
        result['clean'] = not status.stdout
        if result['head'].lower() != expected_sha.lower():
            result['errors'].append('head_mismatch')
        if result['repository'] != expected_repo.lower():
            result['errors'].append('repository_mismatch')
        if not result['clean']:
            result['errors'].append('dirty_checkout')
    except (OSError, ValueError, subprocess.SubprocessError):
        result['errors'].append('git_inspection_failed')
    result['ok'] = not result['errors']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default='.')
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--expected-repository', default='danedormio/dyson-cloud-lab')
    args = parser.parse_args()
    result = inspect_checkout(args.directory, args.expected_sha, args.expected_repository)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
