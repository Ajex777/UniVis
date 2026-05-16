(function () {
  const { fetchJson } = window.UniVisApi;

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

  async function uploadSource(inputFormat, entries, adapterInfo) {
    if (!entries.length) throw new Error("Choose a local source first");
    const options = sourceOptions(adapterInfo);
    if (options.file_extensions?.length && !entries.some((item) => matchesExtension(item, options))) {
      throw new Error("Selected source does not contain supported files");
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

  async function pickDirectory(adapterInfo) {
    if (!window.showDirectoryPicker) {
      throw new Error("This browser does not support safe directory selection");
    }
    const handle = await window.showDirectoryPicker();
    const options = sourceOptions(adapterInfo);
    const topLevelOnly = options.directory_upload === "top_level_matching";
    const entries = topLevelOnly
      ? await pickTopLevelMatchingEntries(handle, options)
      : await walkDirectory(handle, handle.name);
    if (topLevelOnly && !entries.length) {
      const nestedDirs = await countChildDirectories(handle);
      const detail = nestedDirs
        ? "Supported files must be directly inside the selected directory"
        : "Selected directory does not contain supported files";
      return { entries: [], label: `${handle.name} · invalid source`, error: detail };
    }
    return {
      entries,
      label: `${handle.name} · ${entries.length} file(s) selected`,
      error: "",
    };
  }

  async function pickTopLevelMatchingEntries(handle, options) {
    const entries = [];
    for await (const entry of handle.values()) {
      if (entry.kind === "file" && matchesName(entry.name, options)) {
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

  async function pickFile(adapterInfo) {
    const options = sourceOptions(adapterInfo);
    if (!options.supports_file_upload) throw new Error("Selected input does not support file upload");
    const extensions = options.file_extensions || [];
    if (window.showOpenFilePicker) {
      const [handle] = await window.showOpenFilePicker({
        multiple: false,
        types: [{ description: adapterInfo?.label || "Source", accept: { "application/octet-stream": extensions } }],
      });
      return fileSelection(await handle.getFile(), options);
    }
    const file = await browserFileInput(options);
    return fileSelection(file, options);
  }

  function fileSelection(file, options) {
    if (!file || !matchesName(file.name, options)) {
      throw new Error(`Choose a supported file${extensionHint(options)}`);
    }
    return {
      entries: [{ file, relativePath: file.name }],
      label: `${file.name} · single file selected`,
      error: "",
    };
  }

  function browserFileInput(options) {
    return new Promise((resolve, reject) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = (options.file_extensions || []).join(",");
      input.onchange = () => resolve(input.files[0]);
      input.oncancel = () => reject(new Error("File selection cancelled"));
      input.click();
    });
  }

  function sourceOptions(adapterInfo) {
    return adapterInfo?.capabilities?.source || {};
  }

  function matchesExtension(item, options) {
    return matchesName(item.relativePath || item.file.name, options);
  }

  function matchesName(name, options) {
    const extensions = options.file_extensions || [];
    if (!extensions.length) return true;
    return extensions.some((extension) => String(name).toLowerCase().endsWith(extension.toLowerCase()));
  }

  function extensionHint(options) {
    const extensions = options.file_extensions || [];
    return extensions.length ? ` (${extensions.join(", ")})` : "";
  }

  window.UniVisSourceIO = {
    activateWorkspaceSource,
    activateUploadedSource,
    listWorkspaceChildren,
    listWorkspaces,
    listUploadedSources,
    pickDirectory,
    pickFile,
    uploadSource,
  };
})();
