(function () {
  const { fetchJson } = window.UniVisApi;

  /**
   * Convert one active episode through a registered exporter.
   * Input: episode id, exporter name, and optional relative output subpath.
   * Output: Conversion report payload.
   */
  function convertEpisode(episodeId, exporterName, outputSubpath, preprocessors) {
    return fetchJson(`/api/conversions/episodes/${episodeId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exporter_name: exporterName, output_subpath: outputSubpath || "", preprocessors: preprocessors || [] }),
    });
  }

  /**
   * Convert all accepted episodes from the active source.
   * Input: exporter name and optional relative output subpath.
   * Output: Conversion report payload.
   */
  function convertAccepted(exporterName, outputSubpath, preprocessors) {
    return fetchJson("/api/conversions/accepted", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exporter_name: exporterName, output_subpath: outputSubpath || "", preprocessors: preprocessors || [] }),
    });
  }

  function getConfig() {
    return fetchJson("/api/conversions/config");
  }

  function listJobs() {
    return fetchJson("/api/conversions/jobs");
  }

  window.UniVisConversionIO = { convertAccepted, convertEpisode, getConfig, listJobs };
})();
