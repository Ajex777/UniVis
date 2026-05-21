(function () {
  const h = React.createElement;

  /**
   * Render episode annotation editing controls with batch apply support.
   * Input: annotation, callbacks, message, and batch review props.
   * Output: React form for prompt, review status, single save, and batch apply.
   */
  function AnnotationPanel({ annotation, onAnnotation, onSave, message, batchCount, onBatchApply, batchMessage }) {
    return h("div", { className: "form-card" },
      h("strong", null, "Annotation"),
      h("textarea", {
        value: annotation.language_prompt,
        onChange: (event) => onAnnotation({ ...annotation, language_prompt: event.target.value }),
      }),
      h("div", { className: "status-row" }, ["pending", "accepted", "rejected"].map((status) =>
        h("button", {
          key: status,
          className: `ghost ${annotation.review_status === status ? "selected" : ""}`,
          onClick: () => onAnnotation({ ...annotation, review_status: status }),
        }, status),
      )),
      h("button", { className: "primary", onClick: onSave }, "Save"),
      h("button", {
        className: "primary",
        onClick: onBatchApply,
        disabled: !batchCount,
        style: { marginTop: 6, opacity: batchCount ? 1 : 0.5 },
      }, batchCount ? `Apply to selected (${batchCount})` : "Apply to selected"),
      message ? h("p", { className: "meta" }, message) : null,
      batchMessage ? h("p", { className: "meta", style: { color: "var(--accent)" } }, batchMessage) : null,
    );
  }

  window.UniVisAnnotationComponents = { AnnotationPanel };
})();
