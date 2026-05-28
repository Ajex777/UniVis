(function () {
  // This entry file is temporarily above 250 lines because it wires the full
  // single-page shell. Split viewer state and source state during the next UI
  // refactor instead of growing this file further.
  const h = React.createElement;
  const { useEffect, useMemo, useState } = React;
  const { fetchJson, batchAnnotation } = window.UniVisApi;
  const SourceIO = window.UniVisSourceIO;
  const { CameraCard, EpisodeButton, SourceControls, defaultSlots } = window.UniVisComponents;
  const { GripperChart, useTrajectoryPlot } = window.UniVisPlots;

function App() {
  const [episodes, setEpisodes] = useState([]);
  const [registry, setRegistry] = useState(null);
  const [episodeId, setEpisodeId] = useState("");
  const [metadata, setMetadata] = useState(null);
  const [trajectory, setTrajectory] = useState(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [slots, setSlots] = useState({ main: "", left: "", right: "" });
  const [annotation, setAnnotation] = useState(null);
  const [annotationMessage, setAnnotationMessage] = useState("");
  const [message, setMessage] = useState("");
  const [playSpeed, setPlaySpeed] = useState(0);
  const [inputFormat, setInputFormat] = useState("");
  const [outputFormat, setOutputFormat] = useState("");
  const [directoryLabel, setDirectoryLabel] = useState("");
  const [directoryFiles, setDirectoryFiles] = useState([]);
  const [sourceMessage, setSourceMessage] = useState("");
  const [uploadSources, setUploadSources] = useState([]);
  const [selectedUploadId, setSelectedUploadId] = useState("");
  const [sourceMode, setSourceMode] = useState("Mode: no source selected");
  const [sourceRevision, setSourceRevision] = useState(0);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [batchMessage, setBatchMessage] = useState("");
  const [activePreprocessors, setActivePreprocessors] = useState(new Set());
  useTrajectoryPlot("trajectory-plot", trajectory, frameIndex);

  useEffect(() => {
    Promise.all([
      fetchJson("/api/episodes"),
      fetchJson("/api/registry"),
      SourceIO.listUploadedSources(),
    ])
      .then(([items, reg, sources]) => {
        setEpisodes(items);
        setRegistry(reg);
        setUploadSources(sources);
        setSelectedUploadId(sources[0]?.upload_id || "");
        if (items.length) setEpisodeId(items[0].episode_id);
        setInputFormat(reg.input_adapters[0]?.name || "");
        setOutputFormat(reg.output_exporters[0]?.name || "");
      }).catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (!episodeId) return;
    setMetadata(null);
    setTrajectory(null);
    setAnnotation(null);
    setAnnotationMessage("");
    Promise.all([
      fetchJson(`/api/episodes/${episodeId}/metadata`),
      fetchJson(`/api/episodes/${episodeId}/trajectory`),
    ]).then(([meta, traj]) => {
      setMetadata(meta);
      setTrajectory(traj);
      setAnnotation(meta.annotation);
      setSlots(defaultSlots(meta.cameras));
      setFrameIndex(0);
    }).catch((error) => setMessage(error.message));
  }, [episodeId, sourceRevision]);

  useEffect(() => {
    if (!metadata || playSpeed <= 0) return undefined;
    const intervalMs = Math.max(40, 1000 / (metadata.fps * playSpeed));
    const timer = window.setInterval(() => {
      setFrameIndex((value) => (value + 1) % metadata.num_frames);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [metadata, playSpeed]);

  const currentReason = useMemo(() => {
    if (!trajectory?.reachability) return "";
    return trajectory.reachability.reasons[frameIndex] || "";
  }, [trajectory, frameIndex]);

  const selectedInputInfo = useMemo(() => registry?.input_adapters?.find((item) => item.name === inputFormat) || null, [registry, inputFormat]);

  const toggleEpisodeSelection = (id) => setSelectedIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const batchApplyAnnotation = async () => {
    if (selectedIds.size === 0) return;
    try {
      const result = await batchAnnotation([...selectedIds], annotation);
      setBatchMessage(`Applied to ${result.ok}/${result.total} episodes`);
      const updated = {};
      for (const [id, entry] of Object.entries(result.results))
        if (entry.status === "ok") updated[id] = entry.annotation;
      setEpisodes((items) => items.map((item) =>
        updated[item.episode_id] ? { ...item, annotation: updated[item.episode_id] } : item));
      if (updated[episodeId]) setAnnotation(updated[episodeId]);
    } catch (error) { setBatchMessage(error.message); }
  };

  const saveAnnotation = async () => {
    const saved = await fetchJson(`/api/episodes/${episodeId}/annotation`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(annotation),
    });
    setAnnotation(saved);
    setEpisodes((items) => items.map((item) => item.episode_id === episodeId ? { ...item, annotation: saved } : item));
    setAnnotationMessage("Annotation saved");
  };

  const uploadSource = async () => {
    try {
      setMessage(`Uploading ${directoryFiles.length} file(s)...`);
      const payload = await window.UniVisLoading.withLoading("Uploading and loading episodes...", () => SourceIO.uploadSource(inputFormat, directoryFiles, selectedInputInfo));
      await applySourcePayload(payload, "Mode: upload fallback");
      const sources = await SourceIO.listUploadedSources();
      setUploadSources(sources);
      setSelectedUploadId(sources[0]?.upload_id || "");
    } catch (error) {
      setSourceMessage(error.message);
      setMessage(error.message);
    }
  };

  const pickDirectory = async () => {
    try {
      applySelection(await SourceIO.pickDirectory(selectedInputInfo));
    } catch (error) {
      if (error.name !== "AbortError") {
        setSourceMessage(error.message);
        setMessage(error.message);
      }
    }
  };
  const pickFile = async () => {
    try {
      applySelection(await SourceIO.pickFile(selectedInputInfo));
    } catch (error) {
      setSourceMessage(error.message);
      setMessage(error.message);
    }
  };
  const activateUploadedSource = async () => {
    if (!selectedUploadId) return;
    try {
      const payload = await window.UniVisLoading.withLoading("Loading uploaded source...", () => SourceIO.activateUploadedSource(selectedUploadId));
      await applySourcePayload(payload, "Mode: uploaded source");
    } catch (error) {
      setSourceMessage(error.message);
      setMessage(error.message);
    }
  };

  const applySelection = (selection) => {
    setDirectoryFiles(selection.entries);
    setDirectoryLabel(selection.label);
    setSourceMessage(selection.error || "");
    setMessage(selection.error || "");
  };

  const applySourcePayload = async (payload, modeText) => {
    const items = payload.episodes || [];
    setEpisodes(items);
    setEpisodeId(items[0]?.episode_id || "");
    setSelectedIds(new Set());
    setSourceMessage("");
    setSourceMode(modeText || payload.mode || "Mode: source selected");
    setSourceRevision((value) => value + 1);
    setMessage(`Loaded ${items.length} episode(s)`);
  };

  const sourceControls = h(SourceControls, {
    registry,
    selectedInputInfo,
    inputFormat,
    outputFormat,
    directoryLabel,
    sourceMessage,
    uploadSources,
    selectedUploadId,
    sourceMode,
    onApplySourcePayload: applySourcePayload,
    onPickDirectory: pickDirectory,
    onPickFile: pickFile,
    onSelectedUploadId: setSelectedUploadId,
    onActivateUploadSource: activateUploadedSource,
    onInputFormat: setInputFormat,
    onOutputFormat: setOutputFormat,
    onUploadSource: uploadSource,
  });

  if (!metadata || !annotation) {
    return h("div", { className: "app" },
      h("aside", { className: "sidebar" },
        h("div", { className: "brand" }, h("h1", null, "UniVis"), h("p", null, "PolicyEpisode viewer")),
        sourceControls,
        h("div", { className: "list-header" }, h("strong", null, "Episodes")),
        h("div", { className: "episode-list" }, episodes.map((item) =>
          h(EpisodeButton, {
            key: item.episode_id,
            item,
            active: item.episode_id === episodeId,
            onClick: () => setEpisodeId(item.episode_id),
          }),
        )),
      ),
      h("main", { className: "stage empty-stage" },
        h("section", { className: "panel" },
          h("strong", null, "Choose a data source"),
          h("p", { className: "meta" }, message || "Select a workspace path or use upload fallback."),
        ),
      ),
    );
  }

  return h("div", { className: "app" },
    h("aside", { className: "sidebar" },
      h("div", { className: "brand" }, h("h1", null, "UniVis"), h("p", null, "PolicyEpisode viewer")),
      sourceControls,
      h("div", { className: "list-header" },
        h("strong", null, "Episodes"),
        h("div", { className: "source-row" },
          h("button", { className: "link-button", onClick: () => setSelectedIds(new Set(episodes.map((e) => e.episode_id))) }, "All"),
          h("button", { className: "link-button", onClick: () => setSelectedIds(new Set()) }, "None"),
        ),
      ),
      h("div", { className: "episode-list" }, episodes.map((item) =>
        h(EpisodeButton, {
          key: item.episode_id,
          item,
          active: item.episode_id === episodeId,
          onClick: () => setEpisodeId(item.episode_id),
          selectable: true,
          checked: selectedIds.has(item.episode_id),
          onToggleSelect: () => toggleEpisodeSelection(item.episode_id),
        }),
      )),
    ),
    h("main", { className: "stage" },
      h("section", { className: "viewer-grid" },
        h("div", { className: "panel camera-panel" },
          h(CameraCard, { title: "Main", cameras: metadata.cameras, cameraKey: slots.main, onChange: (value) => setSlots({ ...slots, main: value }), episodeId, frameIndex, sourceRevision }),
          h("div", { className: "wrist-row" },
            h(CameraCard, { title: "Left", cameras: metadata.cameras, cameraKey: slots.left, onChange: (value) => setSlots({ ...slots, left: value }), episodeId, frameIndex, sourceRevision }),
            h(CameraCard, { title: "Right", cameras: metadata.cameras, cameraKey: slots.right, onChange: (value) => setSlots({ ...slots, right: value }), episodeId, frameIndex, sourceRevision }),
          ),
        ),
        h("div", { className: "panel" }, h("div", { id: "trajectory-plot", className: "plot" })),
      ),
      h("section", { className: "panel timeline" },
        h("button", { className: "ghost", onClick: () => setFrameIndex(Math.max(0, frameIndex - 1)) }, "Prev"),
        h("input", { type: "range", min: 0, max: metadata.num_frames - 1, value: frameIndex, onChange: (event) => setFrameIndex(Number(event.target.value)) }),
        h("button", { className: "ghost", onClick: () => setFrameIndex(Math.min(metadata.num_frames - 1, frameIndex + 1)) }, "Next"),
        h("div", { className: "speed-row" }, [0, 0.5, 1, 2, 3].map((speed) =>
          h("button", { key: speed, className: `ghost ${playSpeed === speed ? "selected" : ""}`, onClick: () => setPlaySpeed(speed) }, speed === 0 ? "Pause" : `${speed}x`),
        )),
      ),
    ),
    h("aside", { className: "inspector" },
      h("div", { className: "form-card" }, h("strong", null, metadata.title), h("p", { className: "meta" }, `Frame ${frameIndex + 1}/${metadata.num_frames}`), currentReason ? h("p", { className: "reason" }, currentReason) : null),
      h("div", { className: "form-card" }, h("strong", null, "Gripper"), h(GripperChart, { trajectory, frameIndex })),
      h(window.UniVisConversionComponents.ConversionPanel, { episodeId, outputFormat, onMessage: setMessage, preprocessors: registry?.preprocessors || [], activePreprocessors, onActivePreprocessors: setActivePreprocessors }),
      h(window.UniVisAnnotationComponents.AnnotationPanel, {
        annotation, onAnnotation: setAnnotation, onSave: saveAnnotation,
        message: annotationMessage, batchCount: selectedIds.size,
        onBatchApply: batchApplyAnnotation, batchMessage,
      }),
    ),
  );
}

  ReactDOM.createRoot(document.getElementById("root")).render(h(App));
})();
