#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""
RBAC (Role-Based Access Control) Service Module

This module provides services for managing user groups, group memberships,
and knowledge base permissions. It implements a group-based permission system
where users can belong to multiple groups, and groups can have specific permissions
on knowledge bases.

Permission types:
- can_read: View KB and its contents (documents, chunks)
- can_update: Update KB settings, modify documents and chunks
- can_delete: Delete KB, documents, chunks
- can_create: Add new documents and chunks to KB

Admin groups have full access to all resources regardless of specific permissions.
"""

from typing import List, Dict, Optional, Any
from api.db.db_models import (
    DB, UserGroup, UserGroupMember, GroupKnowledgebasePermission,
    User, Knowledgebase, DEFAULT_ADMIN_GROUP_NAME, DEFAULT_USER_GROUP_NAME
)
from api.db.services.common_service import CommonService
from common.misc_utils import get_uuid
from common.time_utils import current_timestamp, datetime_format
from datetime import datetime

# Status constants
VALID_STATUS = "1"
INVALID_STATUS = "0"


class UserGroupService(CommonService):
    """Service for managing user groups."""
    model = UserGroup

    @classmethod
    @DB.connection_context()
    def get_all_groups(cls) -> List[UserGroup]:
        """Get all valid groups."""
        return list(cls.model.select().where(cls.model.status == VALID_STATUS))

    @classmethod
    @DB.connection_context()
    def get_by_name(cls, name: str) -> Optional[UserGroup]:
        """Get a group by name."""
        return cls.model.get_or_none(
            (cls.model.name == name) & (cls.model.status == VALID_STATUS)
        )

    @classmethod
    @DB.connection_context()
    def get_admin_group(cls) -> Optional[UserGroup]:
        """Get the admin group."""
        return cls.model.get_or_none(
            (cls.model.is_admin == True) & (cls.model.status == VALID_STATUS)
        )

    @classmethod
    @DB.connection_context()
    def get_default_user_group(cls) -> Optional[UserGroup]:
        """Get the default user group for new registrations."""
        return cls.model.get_or_none(
            (cls.model.name == DEFAULT_USER_GROUP_NAME) & (cls.model.status == VALID_STATUS)
        )

    @classmethod
    @DB.connection_context()
    def create_group(cls, name: str, description: str = None, is_admin: bool = False) -> UserGroup:
        """Create a new user group."""
        group_id = get_uuid()
        now = current_timestamp()
        now_date = datetime_format(datetime.now())

        cls.model.create(
            id=group_id,
            name=name,
            description=description,
            is_admin=is_admin,
            status=VALID_STATUS,
            create_time=now,
            create_date=now_date,
            update_time=now,
            update_date=now_date
        )
        return cls.model.get_by_id(group_id)

    @classmethod
    @DB.connection_context()
    def update_group(cls, group_id: str, **kwargs) -> int:
        """Update a group's properties."""
        kwargs["update_time"] = current_timestamp()
        kwargs["update_date"] = datetime_format(datetime.now())
        return cls.model.update(kwargs).where(cls.model.id == group_id).execute()

    @classmethod
    @DB.connection_context()
    def delete_group(cls, group_id: str) -> int:
        """Soft delete a group (set status to invalid)."""
        return cls.update_group(group_id, status=INVALID_STATUS)

    @classmethod
    @DB.connection_context()
    def init_default_groups(cls):
        """Initialize default groups (Administrators and Users) if they don't exist."""
        # Create admin group if not exists
        admin_group = cls.get_by_name(DEFAULT_ADMIN_GROUP_NAME)
        if not admin_group:
            cls.create_group(
                name=DEFAULT_ADMIN_GROUP_NAME,
                description="Administrators have full access to all resources",
                is_admin=True
            )

        # Create default user group if not exists
        user_group = cls.get_by_name(DEFAULT_USER_GROUP_NAME)
        if not user_group:
            cls.create_group(
                name=DEFAULT_USER_GROUP_NAME,
                description="Default group for new users with minimal permissions",
                is_admin=False
            )


class UserGroupMemberService(CommonService):
    """Service for managing user-group memberships."""
    model = UserGroupMember

    @classmethod
    @DB.connection_context()
    def add_user_to_group(cls, user_id: str, group_id: str) -> UserGroupMember:
        """Add a user to a group."""
        # Check if membership already exists
        existing = cls.model.get_or_none(
            (cls.model.user_id == user_id) &
            (cls.model.group_id == group_id) &
            (cls.model.status == VALID_STATUS)
        )
        if existing:
            return existing

        membership_id = get_uuid()
        now = current_timestamp()
        now_date = datetime_format(datetime.now())

        cls.model.create(
            id=membership_id,
            user_id=user_id,
            group_id=group_id,
            status=VALID_STATUS,
            create_time=now,
            create_date=now_date,
            update_time=now,
            update_date=now_date
        )
        return cls.model.get_by_id(membership_id)

    @classmethod
    @DB.connection_context()
    def remove_user_from_group(cls, user_id: str, group_id: str) -> int:
        """Remove a user from a group (soft delete)."""
        return cls.model.update({
            "status": INVALID_STATUS,
            "update_time": current_timestamp(),
            "update_date": datetime_format(datetime.now())
        }).where(
            (cls.model.user_id == user_id) &
            (cls.model.group_id == group_id)
        ).execute()

    @classmethod
    @DB.connection_context()
    def get_user_groups(cls, user_id: str) -> List[UserGroup]:
        """Get all groups a user belongs to."""
        memberships = cls.model.select().where(
            (cls.model.user_id == user_id) & (cls.model.status == VALID_STATUS)
        )
        group_ids = [m.group_id for m in memberships]
        if not group_ids:
            return []
        return list(UserGroup.select().where(
            (UserGroup.id.in_(group_ids)) & (UserGroup.status == VALID_STATUS)
        ))

    @classmethod
    @DB.connection_context()
    def get_group_members(cls, group_id: str) -> List[Dict[str, Any]]:
        """Get all users in a group with their info."""
        memberships = cls.model.select().where(
            (cls.model.group_id == group_id) & (cls.model.status == VALID_STATUS)
        )
        user_ids = [m.user_id for m in memberships]
        if not user_ids:
            return []

        users = User.select().where(
            (User.id.in_(user_ids)) & (User.status == VALID_STATUS)
        )
        return [
            {
                "id": u.id,
                "email": u.email,
                "nickname": u.nickname,
                "avatar": u.avatar
            }
            for u in users
        ]

    @classmethod
    @DB.connection_context()
    def is_user_in_group(cls, user_id: str, group_id: str) -> bool:
        """Check if a user is in a specific group."""
        membership = cls.model.get_or_none(
            (cls.model.user_id == user_id) &
            (cls.model.group_id == group_id) &
            (cls.model.status == VALID_STATUS)
        )
        return membership is not None

    @classmethod
    @DB.connection_context()
    def is_user_admin(cls, user_id: str) -> bool:
        """Check if a user belongs to any admin group."""
        user_groups = cls.get_user_groups(user_id)
        return any(g.is_admin for g in user_groups)

    @classmethod
    @DB.connection_context()
    def add_user_to_default_group(cls, user_id: str) -> Optional[UserGroupMember]:
        """Add a user to the default Users group."""
        default_group = UserGroupService.get_default_user_group()
        if default_group:
            return cls.add_user_to_group(user_id, default_group.id)
        return None


class GroupKnowledgebasePermissionService(CommonService):
    """Service for managing group permissions on knowledge bases."""
    model = GroupKnowledgebasePermission

    @classmethod
    @DB.connection_context()
    def set_permission(
        cls,
        group_id: str,
        kb_id: str,
        can_read: bool = False,
        can_update: bool = False,
        can_delete: bool = False,
        can_create: bool = False
    ) -> GroupKnowledgebasePermission:
        """Set or update permissions for a group on a knowledge base."""
        # Check if permission already exists
        existing = cls.model.get_or_none(
            (cls.model.group_id == group_id) &
            (cls.model.kb_id == kb_id) &
            (cls.model.status == VALID_STATUS)
        )

        now = current_timestamp()
        now_date = datetime_format(datetime.now())

        if existing:
            # Update existing permission
            cls.model.update({
                "can_read": can_read,
                "can_update": can_update,
                "can_delete": can_delete,
                "can_create": can_create,
                "update_time": now,
                "update_date": now_date
            }).where(cls.model.id == existing.id).execute()
            return cls.model.get_by_id(existing.id)
        else:
            # Create new permission
            perm_id = get_uuid()
            cls.model.create(
                id=perm_id,
                group_id=group_id,
                kb_id=kb_id,
                can_read=can_read,
                can_update=can_update,
                can_delete=can_delete,
                can_create=can_create,
                status=VALID_STATUS,
                create_time=now,
                create_date=now_date,
                update_time=now,
                update_date=now_date
            )
            return cls.model.get_by_id(perm_id)

    @classmethod
    @DB.connection_context()
    def remove_permission(cls, permission_id: str) -> int:
        """Remove a permission (soft delete)."""
        return cls.model.update({
            "status": INVALID_STATUS,
            "update_time": current_timestamp(),
            "update_date": datetime_format(datetime.now())
        }).where(cls.model.id == permission_id).execute()

    @classmethod
    @DB.connection_context()
    def remove_all_kb_permissions(cls, kb_id: str) -> int:
        """Remove all permissions for a knowledge base (soft delete)."""
        return cls.model.update({
            "status": INVALID_STATUS,
            "update_time": current_timestamp(),
            "update_date": datetime_format(datetime.now())
        }).where(cls.model.kb_id == kb_id).execute()

    @classmethod
    @DB.connection_context()
    def get_kb_permissions(cls, kb_id: str) -> List[Dict[str, Any]]:
        """Get all permissions for a knowledge base."""
        perms = cls.model.select().where(
            (cls.model.kb_id == kb_id) & (cls.model.status == VALID_STATUS)
        )
        result = []
        for p in perms:
            group = UserGroup.get_or_none(UserGroup.id == p.group_id)
            if group:
                result.append({
                    "id": p.id,
                    "group_id": p.group_id,
                    "group_name": group.name,
                    "kb_id": p.kb_id,
                    "can_read": p.can_read,
                    "can_update": p.can_update,
                    "can_delete": p.can_delete,
                    "can_create": p.can_create
                })
        return result

    @classmethod
    @DB.connection_context()
    def get_group_permissions(cls, group_id: str) -> List[Dict[str, Any]]:
        """Get all knowledge base permissions for a group."""
        perms = cls.model.select().where(
            (cls.model.group_id == group_id) & (cls.model.status == VALID_STATUS)
        )
        result = []
        for p in perms:
            kb = Knowledgebase.get_or_none(Knowledgebase.id == p.kb_id)
            if kb:
                result.append({
                    "id": p.id,
                    "group_id": p.group_id,
                    "kb_id": p.kb_id,
                    "kb_name": kb.name,
                    "can_read": p.can_read,
                    "can_update": p.can_update,
                    "can_delete": p.can_delete,
                    "can_create": p.can_create
                })
        return result


class PermissionService:
    """High-level service for checking user permissions on resources."""

    @classmethod
    @DB.connection_context()
    def get_user_kb_permissions(cls, user_id: str, kb_id: str) -> Dict[str, bool]:
        """
        Get effective permissions for a user on a knowledge base.

        Combines permissions from all groups the user belongs to.
        Admin users automatically get all permissions.

        Returns:
            Dict with can_read, can_update, can_delete, can_create booleans
        """
        # Check if user is admin
        if UserGroupMemberService.is_user_admin(user_id):
            return {
                "can_read": True,
                "can_update": True,
                "can_delete": True,
                "can_create": True,
                "is_admin": True
            }

        # Get all user's groups
        user_groups = UserGroupMemberService.get_user_groups(user_id)
        group_ids = [g.id for g in user_groups]

        if not group_ids:
            return {
                "can_read": False,
                "can_update": False,
                "can_delete": False,
                "can_create": False,
                "is_admin": False
            }

        # Get permissions for these groups on the KB
        permissions = GroupKnowledgebasePermission.select().where(
            (GroupKnowledgebasePermission.group_id.in_(group_ids)) &
            (GroupKnowledgebasePermission.kb_id == kb_id) &
            (GroupKnowledgebasePermission.status == VALID_STATUS)
        )

        # Combine permissions (OR logic - if any group has permission, user has it)
        result = {
            "can_read": False,
            "can_update": False,
            "can_delete": False,
            "can_create": False,
            "is_admin": False
        }

        for perm in permissions:
            result["can_read"] = result["can_read"] or perm.can_read
            result["can_update"] = result["can_update"] or perm.can_update
            result["can_delete"] = result["can_delete"] or perm.can_delete
            result["can_create"] = result["can_create"] or perm.can_create

        return result

    @classmethod
    @DB.connection_context()
    def can_read_kb(cls, user_id: str, kb_id: str) -> bool:
        """Check if user can read a knowledge base."""
        perms = cls.get_user_kb_permissions(user_id, kb_id)
        return perms["can_read"] or perms["is_admin"]

    @classmethod
    @DB.connection_context()
    def can_update_kb(cls, user_id: str, kb_id: str) -> bool:
        """Check if user can update a knowledge base."""
        perms = cls.get_user_kb_permissions(user_id, kb_id)
        return perms["can_update"] or perms["is_admin"]

    @classmethod
    @DB.connection_context()
    def can_delete_kb(cls, user_id: str, kb_id: str) -> bool:
        """Check if user can delete a knowledge base."""
        perms = cls.get_user_kb_permissions(user_id, kb_id)
        return perms["can_delete"] or perms["is_admin"]

    @classmethod
    @DB.connection_context()
    def can_create_in_kb(cls, user_id: str, kb_id: str) -> bool:
        """Check if user can create content in a knowledge base."""
        perms = cls.get_user_kb_permissions(user_id, kb_id)
        return perms["can_create"] or perms["is_admin"]

    @classmethod
    @DB.connection_context()
    def get_accessible_kb_ids(cls, user_id: str, permission_type: str = "read") -> List[str]:
        """
        Get list of KB IDs the user has access to.

        Args:
            user_id: User ID
            permission_type: One of "read", "update", "delete", "create"

        Returns:
            List of knowledge base IDs
        """
        # Admin users can access all KBs
        if UserGroupMemberService.is_user_admin(user_id):
            kbs = Knowledgebase.select(Knowledgebase.id).where(
                Knowledgebase.status == VALID_STATUS
            )
            return [kb.id for kb in kbs]

        # Get user's groups
        user_groups = UserGroupMemberService.get_user_groups(user_id)
        group_ids = [g.id for g in user_groups]

        if not group_ids:
            return []

        # Map permission type to field
        perm_field_map = {
            "read": GroupKnowledgebasePermission.can_read,
            "update": GroupKnowledgebasePermission.can_update,
            "delete": GroupKnowledgebasePermission.can_delete,
            "create": GroupKnowledgebasePermission.can_create
        }
        perm_field = perm_field_map.get(permission_type, GroupKnowledgebasePermission.can_read)

        # Get KB IDs with the requested permission
        permissions = GroupKnowledgebasePermission.select(
            GroupKnowledgebasePermission.kb_id
        ).where(
            (GroupKnowledgebasePermission.group_id.in_(group_ids)) &
            (perm_field == True) &
            (GroupKnowledgebasePermission.status == VALID_STATUS)
        )

        return list(set(p.kb_id for p in permissions))

    @classmethod
    @DB.connection_context()
    def get_user_all_permissions(cls, user_id: str) -> Dict[str, Any]:
        """
        Get all permissions for a user across all knowledge bases.

        Returns:
            Dict with user info, groups, and permissions per KB
        """
        is_admin = UserGroupMemberService.is_user_admin(user_id)
        user_groups = UserGroupMemberService.get_user_groups(user_id)

        result = {
            "user_id": user_id,
            "is_admin": is_admin,
            "groups": [{"id": g.id, "name": g.name, "is_admin": g.is_admin} for g in user_groups],
            "kb_permissions": {}
        }

        if is_admin:
            # Admin has full access to all KBs
            kbs = Knowledgebase.select().where(Knowledgebase.status == VALID_STATUS)
            for kb in kbs:
                result["kb_permissions"][kb.id] = {
                    "kb_name": kb.name,
                    "can_read": True,
                    "can_update": True,
                    "can_delete": True,
                    "can_create": True
                }
        else:
            # Get specific permissions
            group_ids = [g.id for g in user_groups]
            if group_ids:
                permissions = GroupKnowledgebasePermission.select().where(
                    (GroupKnowledgebasePermission.group_id.in_(group_ids)) &
                    (GroupKnowledgebasePermission.status == VALID_STATUS)
                )

                # Combine permissions per KB
                for perm in permissions:
                    kb_id = perm.kb_id
                    if kb_id not in result["kb_permissions"]:
                        kb = Knowledgebase.get_or_none(Knowledgebase.id == kb_id)
                        result["kb_permissions"][kb_id] = {
                            "kb_name": kb.name if kb else "Unknown",
                            "can_read": False,
                            "can_update": False,
                            "can_delete": False,
                            "can_create": False
                        }

                    # OR logic for combining permissions
                    result["kb_permissions"][kb_id]["can_read"] |= perm.can_read
                    result["kb_permissions"][kb_id]["can_update"] |= perm.can_update
                    result["kb_permissions"][kb_id]["can_delete"] |= perm.can_delete
                    result["kb_permissions"][kb_id]["can_create"] |= perm.can_create

        return result

    @classmethod
    @DB.connection_context()
    def can_access_dialog_kbs(cls, user_id: str, kb_ids: List[str]) -> bool:
        """
        Check if user can access all knowledge bases in a list.
        Used for validating dialog/chat assistant creation.

        Args:
            user_id: User ID
            kb_ids: List of KB IDs to check

        Returns:
            True if user has at least read access to all KBs
        """
        if not kb_ids:
            return True

        # Admin can access all
        if UserGroupMemberService.is_user_admin(user_id):
            return True

        accessible_kbs = set(cls.get_accessible_kb_ids(user_id, "read"))
        required_kbs = set(kb_ids)

        return required_kbs.issubset(accessible_kbs)
