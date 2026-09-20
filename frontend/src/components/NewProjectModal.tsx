import { useState } from "react";

type ProjectParticipant = { name: string; role: string };
type ProjectCreatePayload = { name: string; participants: ProjectParticipant[] };

type ParticipantDraft = { name: string; role: "me" | "other" };

const blankParticipant = (): ParticipantDraft => ({ name: "", role: "other" });

export function NewProjectModal({
  onCreated,
  onClose,
}: {
  onCreated: (projectId: number) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [twoPerson, setTwoPerson] = useState(false);
  const [participants, setParticipants] = useState<ParticipantDraft[]>([
    { name: "", role: "me" },
    blankParticipant(),
  ]);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const setParticipant = (i: number, patch: Partial<ParticipantDraft>) => {
    setParticipants((prev) =>
      prev.map((p, idx) => (idx === i ? { ...p, ...patch } : p))
    );
  };

  const validate = (): string[] => {
    const errs: string[] = [];
    if (!name.trim()) errs.push("Project name is required.");
    if (twoPerson) {
      if (!participants[0].name.trim()) errs.push("Your name is required.");
      if (!participants[1].name.trim())
        errs.push("Participant name is required.");
      if (
        participants[0].name.trim() &&
        participants[1].name.trim() &&
        participants[0].name.trim().toLowerCase() ===
          participants[1].name.trim().toLowerCase()
      ) {
        errs.push("Participants must have different names.");
      }
      const meCount = participants.filter((p) => p.role === "me").length;
      if (meCount !== 1) errs.push("Exactly one participant must be 'me'.");
    }
    return errs;
  };

  const handleCreate = async () => {
    const errs = validate();
    setErrors(errs);
    if (errs.length) return;

    const payload: ProjectCreatePayload = {
      name: name.trim(),
      participants: twoPerson
        ? participants.map((p) => ({
            name: p.name.trim(),
            role: p.role,
          }))
        : [{ name: "", role: "me" }],
    };

    setLoading(true);
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setErrors([body.detail || "Failed to create project."]);
        return;
      }
      const data = await res.json();
      onCreated(data.id);
    } catch {
      setErrors(["Network error."]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <h2>New project</h2>
          <button className="ghost" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="card">
          <label className="field">
            <span className="muted">Project name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Q4 Campaign"
            />
          </label>

          <label className="toggle">
            <input
              type="checkbox"
              checked={twoPerson}
              onChange={(e) => setTwoPerson(e.target.checked)}
            />
            <span className="muted">Two-person project</span>
          </label>

          {twoPerson && (
            <>
              {participants.map((p, i) => (
                <div className="row" key={i}>
                  <input
                    type="text"
                    className="grow"
                    value={p.name}
                    placeholder={i === 0 ? "Your name" : "Participant name"}
                    onChange={(e) =>
                      setParticipant(i, { name: e.target.value })
                    }
                  />
                  <select
                    value={p.role}
                    onChange={(e) =>
                      setParticipant(i, {
                        role: e.target.value as "me" | "other",
                      })
                    }
                  >
                    <option value="me">me</option>
                    <option value="other">other</option>
                  </select>
                </div>
              ))}
            </>
          )}
        </div>

        {errors.length > 0 && (
          <div className="error">
            {errors.map((e, i) => (
              <p key={i}>{e}</p>
            ))}
          </div>
        )}

        <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
          <button className="ghost" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button onClick={handleCreate} disabled={loading}>
            {loading ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
