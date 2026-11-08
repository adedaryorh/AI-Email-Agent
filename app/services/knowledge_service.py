import re
from app.core.exceptions import ConflictError, NotFoundError
from app.core.locks import operation_lock
from app.models.agent import AgentPreferences, KnowledgeDocument
from app.repositories.agent_repo import AgentRepository


class KnowledgeService:
    def __init__(self, db):
        self.db = db
        self.repo = AgentRepository(db)

    def save(self, data, key=None):
        with operation_lock(self.db, 5, 0):
            row = self.repo.document(key) if key else None
            if key and not row:
                raise NotFoundError("Knowledge document not found")
            if row:
                self.db.refresh(row)
                if row.version != data.version:
                    raise ConflictError("Document changed; reload first")
                row.version += 1
                row.title, row.content = data.title, data.content
            else:
                if len(self.repo.documents()) >= 500:
                    raise ConflictError("Knowledge base limit is 500 documents")
                row = self.repo.add(KnowledgeDocument(title=data.title, content=data.content))
            self.db.commit()
            return row

    def delete(self, key, version):
        with operation_lock(self.db, 5, 0):
            row = self.repo.document(key)
            if not row:
                raise NotFoundError("Knowledge document not found")
            self.db.refresh(row)
            if row.version != version:
                raise ConflictError("Document changed; reload first")
            self.db.delete(row)
            self.db.commit()

    def preferences(self):
        row = self.repo.preferences()
        return {"instructions": row.instructions if row else "", "version": row.version if row else 0}

    def set_preferences(self, data):
        with operation_lock(self.db, 6, 1):
            row = self.repo.preferences()
            if row:
                self.db.refresh(row)
            if (row.version if row else 0) != data.version:
                raise ConflictError("Preferences changed; reload first")
            if row:
                row.instructions, row.version = data.instructions, row.version + 1
            else:
                self.repo.add(AgentPreferences(id=1, instructions=data.instructions))
            self.db.commit()
            return self.preferences()

    def search(self, query):
        terms = set(re.findall(r"\w{3,}", query.lower()))
        candidates = []
        for doc in self.repo.documents():
            for index, start in enumerate(range(0, len(doc.content), 1200)):
                excerpt = doc.content[start:start + 1500]
                words = set(re.findall(r"\w{3,}", (doc.title + " " + excerpt).lower()))
                score = len(terms & words)
                if score:
                    candidates.append((score, {"id": f"{doc.id}:{doc.version}:{index}", "document_id": doc.id,
                        "version": doc.version, "title": doc.title, "excerpt": excerpt}))
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in candidates[:5]]

    def sources_current(self, sources):
        return all((doc := self.repo.document(source["document_id"])) is not None
                   and doc.version == source["version"] for source in sources)
