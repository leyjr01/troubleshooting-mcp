"""Pre-index redaction; external text remains inert data after redaction."""

import re


class KnowledgeRedactor:
    version = "knowledge-redaction-1"

    def redact(self, text: str) -> str:
        text = re.sub(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)",
            "[REDACTED PRIVATE KEY]",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(
            r"(?i)\b(?:postgres(?:ql)?|redis|mongodb(?:\+srv)?|mysql|https?)://[^\s/]*@",
            "[REDACTED CONNECTION]@",
            text,
        )
        text = re.sub(
            r"(?im)([\"']?(?:password|passwd|pwd|token|api[_ -]?key|client[_ -]?secret|"
            r"authorization|connection[_ -]?string)[\"']?\s*[:=]\s*)[^\r\n,;}]+",
            r"\1[REDACTED]",
            text,
        )
        text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", text)
        text = re.sub(
            r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|"
            r"sk-[A-Za-z0-9_-]+|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[\w-]+\.[\w-]+)\b",
            "[REDACTED TOKEN]",
            text,
        )
        text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[REDACTED EMAIL]", text)
        # Opaque long mixed strings are not needed in operational excerpts.
        text = re.sub(
            r"\b(?=[A-Za-z0-9_+/=-]{32,}\b)(?=[A-Za-z0-9_+/=-]*[A-Za-z])"
            r"(?=[A-Za-z0-9_+/=-]*[0-9])[A-Za-z0-9_+/=-]{32,}\b",
            "[REDACTED OPAQUE VALUE]",
            text,
        )
        return text
