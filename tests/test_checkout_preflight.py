"""Exercise actual temporary Git checkouts and fail-closed CLI evidence."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'checkout_preflight.py'
REPO = 'danedormio/dyson-cloud-lab'


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.DEVNULL).decode().strip()


@pytest.fixture
def checkout(tmp_path):
    tmp_path = tmp_path / 'checkout'
    tmp_path.mkdir()
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'Preflight Test')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    (tmp_path / 'tracked').write_text('baseline\n')
    git(tmp_path, 'add', 'tracked')
    git(tmp_path, 'commit', '-qm', 'fixture')
    git(tmp_path, 'remote', 'add', 'origin', 'https://github.com/' + REPO + '.git')
    return tmp_path, git(tmp_path, 'rev-parse', 'HEAD')


def run(path, sha, repo=REPO):
    completed = subprocess.run([sys.executable, str(SCRIPT), '--directory', str(path),
                                '--expected-sha', sha, '--expected-repository', repo],
                               capture_output=True, text=True, timeout=15)
    return completed, json.loads(completed.stdout)


@pytest.mark.parametrize('origin', ['https://github.com/' + REPO + '.git',
                                   'git@github.com:' + REPO + '.git',
                                   'ssh://git@github.com/' + REPO + '.git'])
def test_clean_exact_checkout_is_read_only(checkout, origin):
    path, sha = checkout
    git(path, 'remote', 'set-url', 'origin', origin)
    index_before = (path / '.git' / 'index').read_bytes()
    result, evidence = run(path, sha)
    assert result.returncode == 0 and evidence['ok']
    assert evidence['head'] == sha and evidence['repository'] == REPO
    assert evidence['clean'] and not evidence['errors']
    assert (path / '.git' / 'index').read_bytes() == index_before
    assert git(path, 'rev-parse', 'HEAD') == sha
    assert git(path, 'status', '--porcelain') == ''


@pytest.mark.parametrize('kind', ['tracked', 'untracked'])
def test_dirty_files_are_preserved_and_rejected(checkout, kind):
    path, sha = checkout
    changed = path / kind
    changed.write_text('owner work\n')
    result, evidence = run(path, sha)
    assert result.returncode == 1 and 'dirty_checkout' in evidence['errors']
    assert changed.read_text() == 'owner work\n'


def test_wrong_sha(checkout):
    path, _ = checkout
    result, evidence = run(path, '0' * 40)
    assert result.returncode == 1 and evidence['errors'] == ['head_mismatch']


@pytest.mark.parametrize('origin', ['https://github.com/another/repo.git',
                                   'https://github.com.evil.invalid/' + REPO,
                                   'file:///tmp/repository'])
def test_wrong_origin(checkout, origin):
    path, sha = checkout
    git(path, 'remote', 'set-url', 'origin', origin)
    result, evidence = run(path, sha)
    assert result.returncode == 1 and 'repository_mismatch' in evidence['errors']


def test_credentials_are_never_reported(checkout):
    path, sha = checkout
    git(path, 'remote', 'set-url', 'origin', 'https://user:TEST_SECRET@github.com/another/repo.git')
    result, evidence = run(path, sha)
    assert result.returncode == 1
    assert 'TEST_SECRET' not in result.stdout + result.stderr
    assert evidence['repository'] == 'another/repo'


@pytest.mark.parametrize('sha', ['abc', 'z' * 40])
def test_malformed_sha(checkout, sha):
    result, evidence = run(checkout[0], sha)
    assert result.returncode == 1 and evidence['errors'] == ['expected_sha_must_be_full_40_hex']


def test_non_repository(tmp_path):
    result, evidence = run(tmp_path, '0' * 40)
    assert result.returncode == 1 and evidence['errors'] == ['git_inspection_failed']


def test_nested_directory_does_not_hide_dirty_files(checkout):
    path, sha = checkout
    nested = path / 'nested'
    nested.mkdir()
    (path / 'outside-nested').write_text('work')
    result, evidence = run(nested, sha)
    assert result.returncode == 1 and 'dirty_checkout' in evidence['errors']
