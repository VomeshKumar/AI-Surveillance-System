import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.database.models import UserModel
from app.routes.auth import (
    ManagedUserCreateRequest,
    ManagedUserUpdateRequest,
    create_managed_user,
    generate_unique_user_identifier,
    update_managed_user,
)


class FakeExecuteResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class FakeSession:
    def __init__(self):
        self.users = {}
        self.next_id = 1
        self.existing_usernames = set()

    def add(self, user):
        if user.id is None:
            user.id = self.next_id
            self.next_id += 1

        self.users[user.id] = user
        self.existing_usernames.add(user.username)

    async def commit(self):
        return None

    async def refresh(self, user):
        self.users[user.id] = user
        self.existing_usernames.add(user.username)

    async def rollback(self):
        return None

    async def get(self, model, user_id):
        return self.users.get(user_id)

    async def execute(self, query):
        compiled_query = str(query.compile(compile_kwargs={"literal_binds": True}))

        for username in self.existing_usernames:
            if username in compiled_query:
                return FakeExecuteResult(object())

        return FakeExecuteResult(None)


class FakeAdminUser:
    username = "ADM001"
    role = "admin"


class AuthRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = FakeSession()
        self.admin = FakeAdminUser()

    async def test_generate_unique_user_identifier_rejects_admin_auto_generation(self):
        with self.assertRaises(HTTPException) as context:
            await generate_unique_user_identifier(self.db, "admin")

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Admin ID must be provided manually")

    async def test_generate_unique_user_identifier_retries_on_collision(self):
        self.db.existing_usernames.update({"OP001", "OP002"})
        generated_id = await generate_unique_user_identifier(self.db, "security_personal")
        self.assertEqual(generated_id, "OP003")

    async def test_create_managed_user_generates_security_identifier(self):
        payload = ManagedUserCreateRequest(
            name="Riya Sharma",
            email="riya@example.com",
            password="secure-pass",
            isActive=True,
        )

        with patch(
            "app.routes.auth.generate_unique_user_identifier",
            new=AsyncMock(return_value="OP001"),
        ):
            created_user = await create_managed_user(
                payload=payload,
                db=self.db,
                current_user=self.admin,
            )

        self.assertEqual(created_user.operatorId, "OP001")
        self.assertEqual(created_user.email, "riya@example.com")

    async def test_update_managed_user_keeps_existing_generated_identifier(self):
        user = UserModel(
            username="OP007",
            full_name="Old Name",
            email="old@example.com",
            hashed_password="hashed",
            role="security_officer",
            is_active=True,
        )
        self.db.add(user)

        payload = ManagedUserUpdateRequest(
            name="Updated Name",
            email="updated@example.com",
            password=None,
            isActive=False,
        )

        updated_user = await update_managed_user(
            user_id=user.id,
            payload=payload,
            db=self.db,
            current_user=self.admin,
        )

        self.assertEqual(updated_user.operatorId, "OP007")
        self.assertEqual(updated_user.name, "Updated Name")
        self.assertFalse(updated_user.isActive)


if __name__ == "__main__":
    unittest.main()
