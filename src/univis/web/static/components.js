(function () {
  const h = React.createElement;
  const { useEffect, useState } = React;
  const SourceIO = window.UniVisSourceIO;

  /**
   * Choose stable default camera slots for main and wrist views.
   * Input: camera metadata list.
   * Output: Object with main, left, and right camera keys.
   */
  function defaultSlots(cameras) {
    const keys = cameras.map((camera) => camera.key);
    return {
      main: keys[0] || "",
      left: keys[1] || keys[0] || "",
      right: keys[2] || keys[1] || keys[0] || "",
    };
  }

  /**
   * Render one selectable camera slot.
   * Input: slot metadata, selected camera, and current frame.
   * Output: React element containing a selector and generated image.
   */
  function CameraCard({ title, cameras, cameraKey, onChange, episodeId, frameIndex, sourceRevision }) {
    return h("div", { className: "camera-card" },
      h("div", { className: "camera-title" },
        h("span", null, title),
        h("select", {
          value: cameraKey,
          onChange: (event) => onChange(event.target.value),
        }, cameras.map((camera) =>
          h("option", { key: camera.key, value: camera.key }, camera.label),
        )),
      ),
      cameraKey ? h("img", {
        alt: `${cameraKey} frame ${frameIndex}`,
        src: `${window.UniVisApi.frameUrl(episodeId, cameraKey, frameIndex)}?v=${sourceRevision || 0}`,
      }) : null,
    );
  }

  /**
   * Render a review-state episode card with optional selection checkbox.
   * Input: episode item, active id, click handler, and selection props.
   * Output: Button element with review status color and text.
   */
  function EpisodeButton({ item, active, onClick, selectable, checked, onToggleSelect }) {
    const reviewStatus = item.annotation?.review_status || "pending";
    return h("button", {
      className: `episode-button ${active ? "active" : ""} review-${reviewStatus}`,
      onClick,
    },
      selectable ? h("input", {
        type: "checkbox",
        className: "episode-check",
        checked: !!checked,
        onChange: onToggleSelect,
        onClick: (event) => event.stopPropagation(),
        title: "Select for batch review",
      }) : null,
      h("strong", null, item.title),
      h("p", { className: "meta" },
        `${item.num_frames} frames · ${item.cameras.length} cameras · ${reviewStatus}`,
      ),
      h("span", { className: "status-pill" }, `Review: ${reviewStatus}`),
    );
  }

  /**
   * Render directory and format controls.
   * Input: registry data, selected values, and update handlers.
   * Output: React controls for Phase 001 source setup.
   */
  function SourceControls(props) {
    const registry = props.registry || { input_adapters: [], output_exporters: [] };
    const sources = props.uploadSources || [];
    const [workspaces, setWorkspaces] = useState([]);
    const [workspaceName, setWorkspaceName] = useState("");
    const [workspacePath, setWorkspacePath] = useState("");
    const [workspaceEntries, setWorkspaceEntries] = useState([]);
    const [selectedPath, setSelectedPath] = useState("");
    const [workspaceMessage, setWorkspaceMessage] = useState("");
    const [showUploadTools, setShowUploadTools] = useState(false);

    useEffect(() => {
      SourceIO.listWorkspaces().then((items) => {
        setWorkspaces(items);
        setWorkspaceName(items[0]?.name || "");
      }).catch((error) => setWorkspaceMessage(error.message));
    }, []);

    useEffect(() => {
      if (!workspaceName) return;
      loadWorkspaceChildren(workspaceName, workspacePath);
    }, [workspaceName, workspacePath]);

    const modeText = props.sourceMode || "Mode: no source selected";

    function loadWorkspaceChildren(name, path) {
      window.UniVisLoading.withLoading("Loading directory...", () => SourceIO.listWorkspaceChildren(name, path))
        .then((payload) => {
          const entries = payload.entries || [];
          setWorkspaceEntries(entries);
          setSelectedPath(entries[0]?.relative_path || "");
          setWorkspaceMessage("");
        })
        .catch((error) => setWorkspaceMessage(error.message));
    }

    function openSelectedPath() {
      const item = workspaceEntries.find((entry) => entry.relative_path === selectedPath);
      if (item?.kind === "directory") setWorkspacePath(item.relative_path);
    }

    async function activateWorkspacePath(path) {
      try {
        const payload = await window.UniVisLoading.withLoading(
          "Loading episodes...",
          () => SourceIO.activateWorkspaceSource(props.inputFormat, workspaceName, path),
        );
        props.onApplySourcePayload(payload, `Mode: workspace · ${workspaceName}:${path || "/"}`);
      } catch (error) {
        setWorkspaceMessage(error.message);
      }
    }

    return h("div", { className: "source-panel" },
      h("p", { className: "meta source-mode" }, modeText),
      h("label", null, "Input format"),
      h("select", {
        value: props.inputFormat,
        onChange: (event) => props.onInputFormat(event.target.value),
      }, registry.input_adapters.map((item) =>
        h("option", { key: item.name, value: item.name }, item.label),
      )),
      h("label", null, "Output format"),
      h("select", {
        value: props.outputFormat,
        onChange: (event) => props.onOutputFormat(event.target.value),
      }, registry.output_exporters.map((item) =>
        h("option", { key: item.name, value: item.name }, item.label),
      )),
      h("label", null, "Workspace source"),
      h("select", {
        value: workspaceName,
        onChange: (event) => {
          setWorkspaceName(event.target.value);
          setWorkspacePath("");
        },
        disabled: !workspaces.length,
      }, workspaces.length ? workspaces.map((item) =>
        h("option", { key: item.name, value: item.name }, item.name),
      ) : h("option", { value: "" }, "No workspace configured")),
      h("p", { className: "meta" }, workspacePath || "/"),
      h("div", { className: "source-row" },
        h("button", {
          className: "ghost",
          onClick: () => setWorkspacePath(parentPath(workspacePath)),
          disabled: !workspacePath,
        }, "Up"),
        h("button", {
          className: "ghost",
          onClick: () => workspaceName && loadWorkspaceChildren(workspaceName, workspacePath),
          disabled: !workspaceName,
        }, "Refresh"),
      ),
      h("select", {
        value: selectedPath,
        onChange: (event) => setSelectedPath(event.target.value),
        disabled: !workspaceEntries.length,
      }, workspaceEntries.length ? workspaceEntries.map((item) =>
        h("option", { key: item.relative_path, value: item.relative_path },
          `${item.kind === "directory" ? "[dir]" : "[file]"} ${item.name}`,
        ),
      ) : h("option", { value: "" }, "No entries")),
      h("div", { className: "source-row" },
        h("button", { className: "ghost", onClick: openSelectedPath, disabled: !selectedPath }, "Open"),
        h("button", { className: "ghost", onClick: () => activateWorkspacePath(workspacePath), disabled: !workspaceName }, "Use current"),
      ),
      h("button", {
        className: "primary",
        onClick: () => activateWorkspacePath(selectedPath || workspacePath),
        disabled: !workspaceName,
      }, "Use selected"),
      workspaceMessage ? h("p", { className: "source-message" }, workspaceMessage) : null,
      h("button", { className: "link-button", onClick: () => setShowUploadTools(!showUploadTools) },
        showUploadTools ? "Hide upload tools" : "Show upload tools"),
      showUploadTools ? h(UploadTools, { ...props, sources }) : null,
    );
  }

  function parentPath(path) {
    const parts = String(path || "").split("/").filter(Boolean);
    parts.pop();
    return parts.join("/");
  }

  function UploadTools(props) {
    const sources = props.sources || [];
    const sourceOptions = props.selectedInputInfo?.capabilities?.source || {};
    return h("div", { className: "upload-tools" },
      h("div", { className: "source-row" },
        h("button", { className: "ghost", onClick: props.onPickDirectory }, "Choose directory"),
        h("button", {
          className: "ghost",
          onClick: props.onPickFile,
          disabled: !sourceOptions.supports_file_upload,
        }, "Choose file"),
      ),
      h("p", { className: "meta" }, props.directoryLabel || "No directory selected"),
      props.sourceMessage ? h("p", { className: "source-message" }, props.sourceMessage) : null,
      h("button", { className: "primary", onClick: props.onUploadSource }, "Upload"),
      h("label", null, "Uploaded sources"),
      h("div", { className: "source-row" },
        h("select", {
          value: props.selectedUploadId,
          onChange: (event) => props.onSelectedUploadId(event.target.value),
          disabled: !sources.length,
        }, sources.length ? sources.map((item) =>
          h("option", { key: item.upload_id, value: item.upload_id },
            `${item.root_label || item.upload_id} · ${item.received_files} file(s)`,
          ),
        ) : h("option", { value: "" }, "No uploaded sources")),
        h("button", {
          className: "ghost",
          onClick: props.onActivateUploadSource,
          disabled: !props.selectedUploadId,
        }, "Load"),
      ),
    );
  }

  window.UniVisComponents = {
    CameraCard,
    EpisodeButton,
    SourceControls,
    defaultSlots,
  };
})();
