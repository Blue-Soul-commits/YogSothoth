import React, { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { RepoGroup } from "../api/types";

export interface GroupsPageProps {
  onSelectGroup: (group: RepoGroup) => void;
}

export const GroupsPage: React.FC<GroupsPageProps> = ({ onSelectGroup }) => {
  const [groups, setGroups] = useState<RepoGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadGroups = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const res = await apiClient.get<RepoGroup[]>("/repo-groups");
      setGroups(res.data);
    } catch (err: any) {
      setMessage(`加载仓库组失败: ${err?.message ?? String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadGroups();
  }, []);

  return (
    <div>
      <h2 style={{ marginBottom: "0.5rem" }}>仓库组</h2>
      <p style={{ fontSize: 13, color: "#a3a3a3", marginBottom: "0.75rem" }}>
        仓库组用于在多个仓库之间进行联动问答，例如旧系统 + 新系统 + 工具库等。
      </p>
      {message && <p style={{ color: "red", marginBottom: "0.5rem" }}>{message}</p>}
      {loading && <p>加载中...</p>}
      {!loading && groups.length === 0 && <p>当前尚无仓库组，请先创建一个。</p>}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: "12px"
        }}
      >
        {groups.map(group => (
          <div
            key={group.id}
            className="panel-card"
            style={{
              cursor: "pointer",
              borderRadius: 14,
              padding: "12px 14px"
            }}
            onClick={() => onSelectGroup(group)}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 6
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 500
                  }}
                >
                  {group.name}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: "#a3a3a3"
                  }}
                >
                  ID：{group.id}
                </div>
              </div>
              <div style={{ fontSize: 12, color: "#a3a3a3" }}>
                成员仓库：{group.repo_ids.length}
              </div>
            </div>
            {group.description && (
              <div
                style={{
                  fontSize: 12,
                  color: "#a3a3a3",
                  marginTop: 4
                }}
              >
                {group.description}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

