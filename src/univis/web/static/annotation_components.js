(function () {
  const h = React.createElement;

  /**
   * Render episode annotation editing controls.
   * Input: annotation payload, update callback, save callback, and local message.
   * Output: React form for prompt and review status editing.
   */
  function AnnotationPanel({ annotation, onAnnotation, onSave, message }) {
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
      message ? h("p", { className: "meta" }, message) : null,
    );
  }

  window.UniVisAnnotationComponents = { AnnotationPanel };
})();
