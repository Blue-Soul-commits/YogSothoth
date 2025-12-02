  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gitUrl.trim()) {
      setError("请填写仓�?URL");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiClient.post("/repos", {
        git_url: gitUrl.trim(),
        id: repoId.trim() || undefined,
        summary: summary.trim() || undefined
      });
      onClose();
    } catch (err: any) {
      setError(`索引仓库失败: ${err?.message ?? String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="panel-card" style={{ maxWidth: 520 }}>
        <div className="panel-card-title">索引仓库</div>
        <div className="panel-card-subtitle">
          输入 Git 仓库地址，系统会自动 clone / 更新，并为其生成代码索引和大纲�?        </div>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12 }}>仓库 URL</label>
            <input
              type="text"
              value={gitUrl}
              onChange={e => setGitUrl(e.target.value)}
              placeholder="例如：https://github.com/owner/repo"
              style={{
                width: "100%",
                marginTop: 4,
                padding: "6px 8px",
                borderRadius: 8,
                border: "1px solid #3a3a3a",
                background: "rgba(5,5,5,0.9)",
                color: "#f5f5f5",
                fontSize: 13
              }}
