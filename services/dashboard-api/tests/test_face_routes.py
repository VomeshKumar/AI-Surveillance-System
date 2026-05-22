import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.database.models import PersonModel
from app.routes.faces import activate_face, deactivate_face, enroll_new_face, get_all_faces, update_face

class FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class FakeExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return FakeScalarResult(self._items)


class FakeSession:
    def __init__(self):
        self.identities = {}
        self.next_id = 1

    def add(self, identity):
        if identity.id is None:
            identity.id = self.next_id
            self.next_id += 1

        now = datetime.now(timezone.utc)
        if identity.created_at is None:
            identity.created_at = now
        if identity.updated_at is None:
            identity.updated_at = now

        self.identities[identity.id] = identity

    async def commit(self):
        return None

    async def refresh(self, identity):
        identity.updated_at = datetime.now(timezone.utc)
        self.identities[identity.id] = identity

    async def rollback(self):
        return None

    async def get(self, model, identity_id):
        return self.identities.get(identity_id)

    async def execute(self, query):
        ordered_items = sorted(self.identities.values(), key=lambda item: (item.updated_at, item.id), reverse=True)
        return FakeExecuteResult(ordered_items)


class FakeAdminUser:
    username = "admin_user"
    role = "admin"


class FakeUploadFile:
    def __init__(self, content: bytes):
        self._content = content

    async def read(self):
        return self._content


class FaceRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = FakeSession()
        self.admin = FakeAdminUser()

    async def test_enroll_new_face_persists_watchlist_fields(self):
        saved_identity = await enroll_new_face(
            name="Ravi Kumar",
            category="suspect",
            image=FakeUploadFile(b"fake-image"),
            db=self.db,
            current_user=self.admin,
        )

        self.assertEqual(saved_identity.name, "Ravi Kumar")
        self.assertEqual(saved_identity.category, "suspect")
        self.assertEqual(saved_identity.registered_by, "admin_user")
        self.assertTrue(saved_identity.is_active)
        self.assertTrue(saved_identity.has_image)

    async def test_update_face_replaces_modified_watchlist_fields(self):
        existing = PersonModel(
            name="Asha",
            category="suspect",
            registered_by="admin_user",
            is_active=True,
        )
        self.db.add(existing)

        updated_identity = await update_face(
            existing.id,
            name="Asha Verma",
            category="priority",
            image=None,
            db=self.db,
            current_user=self.admin,
        )

        self.assertEqual(updated_identity.name, "Asha Verma")
        self.assertEqual(updated_identity.category, "priority")

    async def test_get_all_faces_includes_deactivated_records(self):
        active_identity = PersonModel(
            name="Active Face",
            category="priority",
            registered_by="admin_user",
            is_active=True,
        )
        inactive_identity = PersonModel(
            name="Inactive Face",
            category="suspect",
            registered_by="admin_user",
            is_active=True,
        )
        self.db.add(active_identity)
        self.db.add(inactive_identity)

        await deactivate_face(inactive_identity.id, db=self.db, current_user=self.admin)

        identities = await get_all_faces(
            category=None,
            limit=50,
            offset=0,
            db=self.db,
            current_user=self.admin,
        )

        self.assertEqual(len(identities), 2)
        inactive_record = next(identity for identity in identities if identity.id == inactive_identity.id)
        self.assertFalse(inactive_record.is_active)

    async def test_update_face_raises_for_missing_identity(self):
        with self.assertRaises(HTTPException) as context:
            await update_face(
                999,
                name="Missing",
                category="suspect",
                image=FakeUploadFile(b"missing-image"),
                db=self.db,
                current_user=self.admin,
            )

        self.assertEqual(context.exception.status_code, 404)

    async def test_activate_face_marks_identity_active_again(self):
        identity = PersonModel(
            name="Dormant Face",
            category="suspect",
            registered_by="admin_user",
            is_active=False,
        )
        self.db.add(identity)

        response = await activate_face(identity.id, db=self.db, current_user=self.admin)

        self.assertEqual(response["face_id"], identity.id)
        self.assertTrue(self.db.identities[identity.id].is_active)


if __name__ == "__main__":
    unittest.main()
