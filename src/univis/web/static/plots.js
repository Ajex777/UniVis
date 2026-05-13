(function () {
  /**
   * Draw Plotly 3D trajectory whenever data or frame index changes.
   * Input: DOM id, trajectory payload, and current frame index.
   * Output: Side effect that updates the Plotly scene.
   */
  function useTrajectoryPlot(elementId, trajectory, frameIndex) {
    React.useEffect(() => {
      if (!trajectory || !window.Plotly) return;
      const left = trajectory.left_xyz;
      const right = trajectory.right_xyz;
      const currentLeft = left[frameIndex] || left[0];
      const currentRight = right[frameIndex] || right[0];
      const reachable = trajectory.reachability?.reachable || [];
      const badLeft = left.filter((_, index) => reachable[index] === false);
      const badRight = right.filter((_, index) => reachable[index] === false);
      const trace = (name, points, color, width = 6) => ({
        name,
        type: "scatter3d",
        mode: "lines",
        x: points.map((p) => p[0]),
        y: points.map((p) => p[1]),
        z: points.map((p) => p[2]),
        line: { color, width },
      });
      const marker = (name, point, color) => ({
        name,
        type: "scatter3d",
        mode: "markers",
        x: [point[0]],
        y: [point[1]],
        z: [point[2]],
        marker: { size: 7, color },
      });
      const data = [
        trace("left eef", left, "#14785f"),
        trace("right eef", right, "#b87300"),
        trace("left unreachable", badLeft, "#9b2f3f", 9),
        trace("right unreachable", badRight, "#9b2f3f", 9),
        marker("left current", currentLeft, "#0b4f40"),
        marker("right current", currentRight, "#8f5600"),
      ];
      const layout = {
        margin: { l: 0, r: 0, t: 20, b: 0 },
        paper_bgcolor: "rgba(0,0,0,0)",
        scene: {
          aspectmode: "cube",
          camera: { eye: { x: 1.5, y: 1.4, z: 1.0 } },
        },
        showlegend: true,
        uirevision: "keep-camera",
      };
      Plotly.react(elementId, data, layout, { displaylogo: false, responsive: true });
    }, [elementId, trajectory, frameIndex]);
  }

  /**
   * Render a compact SVG gripper curve.
   * Input: left/right gripper arrays and current frame index.
   * Output: SVG React element.
   */
  function GripperChart({ trajectory, frameIndex }) {
    const h = React.createElement;
    const width = 320;
    const height = 82;
    if (!trajectory) return h("svg", { className: "gripper-chart" });
    const pathFor = (values) => values.map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * width;
      const y = height - 8 - Math.max(0, Math.min(1, value)) * (height - 16);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    const cursorX = (frameIndex / Math.max(1, trajectory.indices.length - 1)) * width;
    return h("svg", { className: "gripper-chart", viewBox: `0 0 ${width} ${height}` },
      h("path", { d: pathFor(trajectory.left_gripper), fill: "none", stroke: "#14785f", strokeWidth: 3 }),
      h("path", { d: pathFor(trajectory.right_gripper), fill: "none", stroke: "#b87300", strokeWidth: 3 }),
      h("line", { x1: cursorX, x2: cursorX, y1: 0, y2: height, stroke: "#1c2830", strokeWidth: 1 }),
    );
  }

  window.UniVisPlots = { GripperChart, useTrajectoryPlot };
})();
