(function () {
  const h = React.createElement;
  const { useEffect, useMemo, useState } = React;
  const { fetchJson } = window.UniVisApi;
  const { CameraCard, EpisodeButton, SourceControls, defaultSlots } = window.UniVisComponents;
  const { GripperChart, useTrajectoryPlot } = window.UniVisPlots;

/**
 * Main UniVis React component.
 * Input: None.
 * Output: Phase 001 web viewer bound to fake PolicyEpisode API data.
 */
function App() {
  const [episodes, setEpisodes] = useState([]);
  const [registry, setRegistry] = useState(null);
  const [episodeId, setEpisodeId] = useState("");
  const [metadata, setMetadata] = useState(null);
  const [trajectory, setTrajectory] = useState(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [slots, setSlots] = useState({ main: "", left: "", right: "" });
  const [annotation, setAnnotation] = useState(null);
  const [message, setMessage] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(0);
  const [inputFormat, setInputFormat] = useState("FakePolicyEpisodeAdapter");
  const [outputFormat, setOutputFormat] = useState("HDF5EpisodeExporter");
  const [directoryLabel, setDirectoryLabel] = useState("");
  useTrajectoryPlot("trajectory-plot", trajectory, frameIndex);

  useEffect(() => {
    Promise.all([fetchJson("/api/episodes"), fetchJson("/api/registry")])
      .then(([items, reg]) => {
        setEpisodes(items);
        setRegistry(reg);
        if (items.length) setEpisodeId(items[0].episode_id);
      }).catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (!episodeId) return;
    setMetadata(null);
    setTrajectory(null);
    setAnnotation(null);
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
  }, [episodeId]);

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

  const saveAnnotation = async () => {
    const saved = await fetchJson(`/api/episodes/${episodeId}/annotation`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(annotation),
    });
    setAnnotation(saved);
    setMessage("Annotation saved");
  };

  const onDirectoryChange = (event) => {
    const files = Array.from(event.target.files || []);
    const first = files[0]?.webkitRelativePath || files[0]?.name || "";
    const root = first.includes("/") ? first.split("/")[0] : "selected directory";
    setDirectoryLabel(files.length ? `${root} · ${files.length} files selected` : "");
  };

  if (!metadata || !annotation) {
    return h("div", { className: "app" },
      h("div", { className: "brand" }, h("h1", null, "UniVis"), h("p", null, "Loading...")),
    );
  }

  return h("div", { className: "app" },
    h("aside", { className: "sidebar" },
      h("div", { className: "brand" }, h("h1", null, "UniVis"), h("p", null, "PolicyEpisode viewer")),
      h(SourceControls, {
        registry,
        inputFormat,
        outputFormat,
        directoryLabel,
        onDirectoryChange,
        onInputFormat: setInputFormat,
        onOutputFormat: setOutputFormat,
      }),
      h("div", { className: "list-header" },
        h("strong", null, "Episodes"),
        h("button", { className: "link-button", onClick: () => setCollapsed(!collapsed) }, collapsed ? "Expand" : "Collapse"),
      ),
      collapsed ? null : h("div", { className: "episode-list" }, episodes.map((item) =>
        h(EpisodeButton, {
          key: item.episode_id,
          item,
          active: item.episode_id === episodeId,
          onClick: () => setEpisodeId(item.episode_id),
        }),
      )),
    ),
    h("main", { className: "stage" },
      h("section", { className: "viewer-grid" },
        h("div", { className: "panel camera-panel" },
          h(CameraCard, { title: "Main", cameras: metadata.cameras, cameraKey: slots.main, onChange: (value) => setSlots({ ...slots, main: value }), episodeId, frameIndex }),
          h("div", { className: "wrist-row" },
            h(CameraCard, { title: "Left", cameras: metadata.cameras, cameraKey: slots.left, onChange: (value) => setSlots({ ...slots, left: value }), episodeId, frameIndex }),
            h(CameraCard, { title: "Right", cameras: metadata.cameras, cameraKey: slots.right, onChange: (value) => setSlots({ ...slots, right: value }), episodeId, frameIndex }),
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
      h("div", { className: "form-card" },
        h("strong", null, "Annotation"),
        h("textarea", { value: annotation.language_prompt, onChange: (event) => setAnnotation({ ...annotation, language_prompt: event.target.value }) }),
        h("div", { className: "status-row" }, ["pending", "accepted", "rejected"].map((status) =>
          h("button", { key: status, className: `ghost ${annotation.review_status === status ? "selected" : ""}`, onClick: () => setAnnotation({ ...annotation, review_status: status }) }, status),
        )),
        h("button", { className: "primary", onClick: saveAnnotation }, "Save"),
        h("p", { className: "meta" }, message),
      ),
    ),
  );
}

  ReactDOM.createRoot(document.getElementById("root")).render(h(App));
})();
