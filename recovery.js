/* One private, transactional backup per browser origin. Never log credentials. */
window.RecoveryBackup = (() => {
  let db, record;
  const format = 'dyson-private-backup-v1';
  function transaction(mode, operation) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('backups', mode);
      let value;
      tx.oncomplete = () => resolve(value);
      tx.onerror = () => reject(Error('Browser backup storage is unavailable'));
      tx.onabort = () => reject(Error('Browser backup could not be saved'));
      try { operation(tx.objectStore('backups'), result => { value = result; }); }
      catch { tx.abort(); }
    });
  }
  function credential() {
    const bytes = crypto.getRandomValues(new Uint8Array(32));
    return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  async function write(next) {
    await transaction('readwrite', store => store.put(next, 'current'));
    record = next; // Only acknowledge the backup after IndexedDB commits it.
  }
  async function init() {
    if (record) return record;
    db = await new Promise((resolve, reject) => {
      const request = indexedDB.open('dyson-private-backups', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('backups');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(Error('Browser backup storage is unavailable'));
      request.onblocked = () => reject(Error('Close older simulator tabs to enable backups'));
    });
    // A single read/write transaction avoids two first-open tabs creating
    // different recovery owners and racing to overwrite the same backup.
    record = await transaction('readwrite', (store, done) => {
      const request = store.get('current');
      request.onsuccess = () => {
        try {
          const current = request.result || {format, credential: credential(), capsule: null};
          if (!request.result) store.put(current, 'current');
          done(current);
        } catch { store.transaction.abort(); }
      };
    });
    return record;
  }
  async function refresh() {
    await init();
    record = await transaction('readonly', (store, done) => {
      const request = store.get('current');
      request.onsuccess = () => done(request.result);
    });
    if (!record) throw Error('Browser backup missing; reload before continuing');
    return record;
  }
  async function accept(capsule, proof) {
    await init();
    if (!capsule) return false;
    const previous = await refresh();
    const chosen = proof || previous.credential;
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(chosen));
    const owner = [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2,'0')).join('');
    if (owner !== capsule.owner) throw Error('Backup owner changed; reconnect before continuing');
    record = await transaction('readwrite', (store, done) => {
      const request = store.get('current');
      request.onsuccess = () => {
        try {
          const current = request.result;
          if (!proof && current.credential !== chosen) {
            store.transaction.abort();
            return;
          }
          // A late response from another tab must not overwrite newer recovery.
          if (current.capsule?.owner === owner &&
              (current.capsule.revision > capsule.revision ||
               (current.capsule.revision === capsule.revision && current.capsule.issued_at > capsule.issued_at))) {
            done(current);
            return;
          }
          const next = {format, credential: chosen, capsule};
          store.put(next, 'current');
          done(next);
        } catch { store.transaction.abort(); }
      };
    });
    return true;
  }
  async function reset() {
    await init();
    await write({format, credential: credential(), capsule: null});
  }
  async function download() {
    const current = await refresh();
    if (!current.capsule) throw Error('No recovery backup is available yet');
    const url = URL.createObjectURL(new Blob([JSON.stringify(current)], {type:'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'dyson-private-recovery.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 3000);
  }
  return {init, refresh, accept, reset, download, format};
})();
