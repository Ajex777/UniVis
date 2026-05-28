(function () {
  const h = React.createElement;
  const { useEffect, useState } = React;
  const ConversionIO = window.UniVisConversionIO;

  function PreprocessorCheckboxes({ items, active, onChange }) {
    if (!items?.length) return null;
    return h("div", { className: "form-card" },
      h("strong", null, "Preprocessing"),
      items.map((pp) =>
        h("label", { key: pp.name, className: "checkbox-label" },
          h("input", {
            type: "checkbox",
            checked: active.has(pp.name),
            onChange: () => {
              const next = new Set(active);
              if (next.has(pp.name)) next.delete(pp.name); else next.add(pp.name);
              onChange(next);
            },
          }),
          ` ${pp.label}`,
        ),
      ),
    );
  }

  /**
   * Render active-source conversion controls.
   * Input: selected episode id, selected exporter name, and message handler.
   * Output: React panel for single and accepted-only batch conversion.
   */
  function ConversionPanel({ episodeId, outputFormat, onMessage, preprocessors, activePreprocessors, onActivePreprocessors }) {
    const [outputConfig, setOutputConfig] = useState(null);
    const [outputSubpath, setOutputSubpath] = useState("");
    const [busy, setBusy] = useState(false);
    const [jobs, setJobs] = useState([]);

    useEffect(() => {
      ConversionIO.getConfig().then(setOutputConfig).catch((_error) => setOutputConfig(null));
      refreshJobs();
      const timer = window.setInterval(refreshJobs, 1000);
      return () => window.clearInterval(timer);
    }, []);

    async function runConversion(scope) {
      if (!outputFormat) return;
      setBusy(true);
      try {
        const payload = scope === "accepted"
          ? await ConversionIO.convertAccepted(outputFormat, outputSubpath, [...activePreprocessors])
          : await ConversionIO.convertEpisode(episodeId, outputFormat, outputSubpath, [...activePreprocessors]);
        setJobs((items) => [payload, ...items.filter((item) => item.job_id !== payload.job_id)]);
        onMessage(`Export job started: ${payload.job_id.slice(0, 8)}`);
      } catch (error) {
        onMessage(error.message);
      } finally {
        setBusy(false);
      }
    }

    async function refreshJobs() {
      try {
        setJobs(await ConversionIO.listJobs());
      } catch (_error) {
        setJobs([]);
      }
    }

    return h(React.Fragment, null,
      h(PreprocessorCheckboxes, { items: preprocessors, active: activePreprocessors, onChange: onActivePreprocessors }),
      h("div", { className: "form-card" },
        h("strong", null, "Conversion"),
        h("p", { className: "meta" }, `Output root: ${outputConfig?.root || "loading..."}`),
        h("input", {
          value: outputSubpath,
          placeholder: "Relative output subpath, e.g. sort_book_0509/pos1",
          onChange: (event) => setOutputSubpath(event.target.value),
        }),
        h("div", { className: "status-row" },
          h("button", {
            className: "primary",
            disabled: busy || !episodeId || !outputFormat,
            onClick: () => runConversion("current"),
          }, "Export current"),
          h("button", {
            className: "ghost",
            disabled: busy || !outputFormat,
            onClick: () => runConversion("accepted"),
          }, "Export accepted"),
        ),
      ),
      h(ConversionRecords, { jobs }),
    );
  }

  function ConversionRecords({ jobs }) {
    const visible = (jobs || []).slice(0, 5);
    if (!visible.length) return null;
    return h("div", { className: "conversion-records" },
      h("strong", null, "Exports"),
      visible.map((job) => {
        const percent = Math.round((job.progress || 0) * 100);
        return h("div", { key: job.job_id, className: "conversion-record" },
          h("div", { className: "record-line" },
            h("span", null, `${job.scope} · ${job.status}`),
            h("span", null, `${percent}%`),
          ),
          h("div", { className: "progress-track" },
            h("div", { className: "progress-fill", style: { width: `${percent}%` } }),
          ),
          h("p", { className: "meta" },
            `${job.succeeded}/${job.total} succeeded · ${job.output_root}`,
          ),
        );
      }),
    );
  }

  window.UniVisConversionComponents = { ConversionPanel, ConversionRecords };
})();
