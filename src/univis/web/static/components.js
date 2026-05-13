(function () {
  const h = React.createElement;

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
  function CameraCard({ title, cameras, cameraKey, onChange, episodeId, frameIndex }) {
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
        src: window.UniVisApi.frameUrl(episodeId, cameraKey, frameIndex),
      }) : null,
    );
  }

  /**
   * Render a conversion-state episode card.
   * Input: episode item, active id, and click handler.
   * Output: Button element with status color/progress styling.
   */
  function EpisodeButton({ item, active, onClick }) {
    const conversion = item.conversion || { status: "pending", progress: 0 };
    const progress = Math.max(0, Math.min(1, conversion.progress || 0));
    const style = { "--progress": `${Math.round(progress * 100)}%` };
    return h("button", {
      className: `episode-button ${active ? "active" : ""} ${conversion.status}`,
      style,
      onClick,
    },
      h("strong", null, item.title),
      h("p", { className: "meta" },
        `${item.num_frames} frames · ${item.cameras.length} cameras`,
      ),
      h("span", { className: "status-pill" }, conversion.status),
    );
  }

  /**
   * Render directory and format controls.
   * Input: registry data, selected values, and update handlers.
   * Output: React controls for Phase 001 source setup.
   */
  function SourceControls(props) {
    const registry = props.registry || { input_adapters: [], output_exporters: [] };
    return h("div", { className: "source-panel" },
      h("label", null, "Local directory"),
      h("input", {
        type: "file",
        webkitdirectory: "true",
        directory: "true",
        multiple: true,
        onChange: props.onDirectoryChange,
      }),
      h("p", { className: "meta" }, props.directoryLabel || "No directory selected"),
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
    );
  }

  window.UniVisComponents = {
    CameraCard,
    EpisodeButton,
    SourceControls,
    defaultSlots,
  };
})();
