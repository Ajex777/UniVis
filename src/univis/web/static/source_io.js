(function () {
  const { fetchJson } = window.UniVisApi;
  const hdf5Pattern = /\.(hdf5|h5)$/i;

  async function listUploadedSources() {
    return fetchJson("/api/uploads/sources");
  }

  async function activateUploadedSource(uploadId) {
    return fetchJson(`/api/uploads/sources/${uploadId}/activate`, { method: "POST" });
  }

  async function listWorkspaces() {
    return fetchJson("/api/workspaces");
  }

  async function listWorkspaceChildren(workspace, path) {
    const query = new URLSearchParams({ path: path || "" });
    return fetchJson(`/api/workspaces/${encodeURIComponent(workspace)}/children?${query}`);
  }

  async function activateWorkspaceSource(inputFormat, workspace, relativePath) {
    return fetchJson("/api/workspaces/source", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_adapter: inputFormat,
        workspace,
        relative_path: relativePath || "",
      }),
    });
  }

  async function uploadSource(inputFormat, entries) {
    if (!entries.length) throw new Error("Choose a local source first");
    if (inputFormat === "HDF5EpisodeAdapter" && !entries.some(isHdf5Entry)) {
      throw new Error("Selected source does not contain HDF5 files");
    }
    const totalSize = entries.reduce((sum, item) => sum + item.file.size, 0);
    const first = entries[0]?.relativePath || entries[0]?.file.name || "";
    const root = first.includes("/") ? first.split("/")[0] : first;
    const upload = await fetchJson("/api/uploads/datasets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_adapter: inputFormat,
        root_label: root,
        file_count: entries.length,
        total_size: totalSize,
      }),
    });
    const formData = new FormData();
    entries.forEach((item) => {
      formData.append("files", item.file, item.file.name);
      formData.append("relative_paths", item.relativePath);
    });
    await fetchJson(`/api/uploads/${upload.upload_id}/files`, {
      method: "POST",
      body: formData,
    });
    return fetchJson(`/api/uploads/${upload.upload_id}/complete`, { method: "POST" });
  }

  async function pickDirectory(inputFormat) {
    if (!window.showDirectoryPicker) {
      throw new Error("This browser does not support safe directory selection");
    }
    const handle = await window.showDirectoryPicker();
    const entries = inputFormat === "HDF5EpisodeAdapter"
      ? await pickTopLevelHdf5Entries(handle)
      : await walkDirectory(handle, handle.name);
    if (inputFormat === "HDF5EpisodeAdapter" && !entries.length) {
      const nestedDirs = await countChildDirectories(handle);
      const detail = nestedDirs
        ? "HDF5 files must be directly inside the selected directory"
        : "Selected directory does not contain HDF5 files";
      return { entries: [], label: `${handle.name} · invalid for HDF5`, error: detail };
    }
    return {
      entries,
      label: `${handle.name} · ${entries.length} file(s) selected`,
      error: "",
    };
  }

  async function pickTopLevelHdf5Entries(handle) {
    const entries = [];
    for await (const entry of handle.values()) {
      if (entry.kind === "file" && hdf5Pattern.test(entry.name)) {
        entries.push({ file: await entry.getFile(), relativePath: `${handle.name}/${entry.name}` });
      }
    }
    return entries;
  }

  async function walkDirectory(handle, prefix) {
    const entries = [];
    for await (const entry of handle.values()) {
      const relativePath = `${prefix}/${entry.name}`;
      if (entry.kind === "file") {
        entries.push({ file: await entry.getFile(), relativePath });
      } else {
        entries.push(...await walkDirectory(entry, relativePath));
      }
    }
    return entries;
  }

  async function countChildDirectories(handle) {
    let count = 0;
    for await (const entry of handle.values()) {
      if (entry.kind === "directory") count += 1;
    }
    return count;
  }

  async function pickHdf5File() {
    if (window.showOpenFilePicker) {
      const [handle] = await window.showOpenFilePicker({
        multiple: false,
        types: [{ description: "HDF5", accept: { "application/octet-stream": [".hdf5", ".h5"] } }],
      });
      return fileSelection(await handle.getFile());
    }
    const file = await browserFileInput();
    return fileSelection(file);
  }

  function fileSelection(file) {
    if (!file || !hdf5Pattern.test(file.name)) throw new Error("Choose a .hdf5 or .h5 file");
    return {
      entries: [{ file, relativePath: file.name }],
      label: `${file.name} · single file selected`,
      error: "",
    };
  }

  function browserFileInput() {
    return new Promise((resolve, reject) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".hdf5,.h5";
      input.onchange = () => resolve(input.files[0]);
      input.oncancel = () => reject(new Error("File selection cancelled"));
      input.click();
    });
  }

  function isHdf5Entry(item) {
    return hdf5Pattern.test(item.relativePath || item.file.name);
  }

  window.UniVisSourceIO = {
    activateWorkspaceSource,
    activateUploadedSource,
    listWorkspaceChildren,
    listWorkspaces,
    listUploadedSources,
    pickDirectory,
    pickHdf5File,
    uploadSource,
  };
})();
