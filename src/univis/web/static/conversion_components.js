(function () {
  const h = React.createElement;
  const { useEffect, useState } = React;
  const ConversionIO = window.UniVisConversionIO;

  /**
   * Render active-source conversion controls.
   * Input: selected episode id, selected exporter name, and message handler.
   * Output: React panel for single and accepted-only batch conversion.
   */
  function ConversionPanel({ episodeId, outputFormat, onMessage }) {
    const [outputRoot, setOutputRoot] = useState("");
    const [busy, setBusy] = useState(false);
    const [jobs, setJobs] = useState([]);

    useEffect(() => {
      refreshJobs();
      const timer = window.setInterval(refreshJobs, 1000);
      return () => window.clearInterval(timer);
    }, []);

    async function runConversion(scope) {
      if (!outputFormat) return;
      setBusy(true);
      try {
        const payload = scope === "accepted"
          ? await ConversionIO.convertAccepted(outputFormat, outputRoot)
          : await ConversionIO.convertEpisode(episodeId, outputFormat, outputRoot);
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
      h("div", { className: "form-card" },
        h("strong", null, "Conversion"),
        h("input", {
          value: outputRoot,
          placeholder: "Output directory (default .univis/exports)",
          onChange: (event) => setOutputRoot(event.target.value),
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
