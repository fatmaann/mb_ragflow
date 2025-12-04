# RAGFlow Refactoring Plan

## Overview

This plan outlines the complete refactoring of RAGFlow to:
1. Keep only specific API endpoints (Dataset, Document, Chunk, Chat Assistant, Session management)
2. Implement a new RBAC (Role-Based Access Control) system with Groups
3. Remove all LLM/Embedding providers except HuggingFace and OpenRouter
4. Update frontend to reflect all backend changes

---

## Phase 1: Database Schema Changes (RBAC)

### 1.1 New Database Models

Create new tables in `api/db/db_models.py`:

```python
class UserGroup(DataBaseModel):
    """User groups for RBAC"""
    id = CharField(max_length=32, primary_key=True)
    name = CharField(max_length=128, unique=True)
    description = TextField(null=True)
    is_admin = BooleanField(default=False)  # Admin group has full access
    create_time = DateTimeField()
    update_time = DateTimeField()

class UserGroupMember(DataBaseModel):
    """Many-to-many: Users in Groups"""
    id = CharField(max_length=32, primary_key=True)
    user_id = CharField(max_length=32, index=True)
    group_id = CharField(max_length=32, index=True)
    create_time = DateTimeField()

class GroupKnowledgebasePermission(DataBaseModel):
    """Permissions for Group on Knowledgebase"""
    id = CharField(max_length=32, primary_key=True)
    group_id = CharField(max_length=32, index=True)
    kb_id = CharField(max_length=32, index=True)
    can_read = BooleanField(default=False)
    can_update = BooleanField(default=False)  # Update KB settings
    can_delete = BooleanField(default=False)  # Delete KB
    can_create = BooleanField(default=False)  # Add documents/chunks
    create_time = DateTimeField()
    update_time = DateTimeField()

    class Meta:
        indexes = (
            (('group_id', 'kb_id'), True),  # Unique constraint
        )
```

### 1.2 Database Migration

Create migration script to:
1. Create new tables (UserGroup, UserGroupMember, GroupKnowledgebasePermission)
2. Create default "Administrators" group with `is_admin=True`
3. Create default "Users" group for new registrations
4. Migrate existing users to appropriate groups

---

## Phase 2: Backend API Cleanup

### 2.1 API Endpoints to KEEP

#### Dataset Management (`api/apps/kb_app.py`)
- `POST /api/v1/kb/create` - Create dataset
- `POST /api/v1/kb/update` - Update dataset
- `POST /api/v1/kb/rm` - Delete datasets
- `POST /api/v1/kb/list` - List datasets
- `GET /api/v1/kb/<kb_id>/knowledge_graph` - Get knowledge graph
- `DELETE /api/v1/kb/<kb_id>/knowledge_graph` - Delete knowledge graph
- `POST /api/v1/kb/run_graphrag` - Construct knowledge graph
- `GET /api/v1/kb/graphrag_progress` - Get KG construction status
- `POST /api/v1/kb/run_raptor` - Construct RAPTOR
- `GET /api/v1/kb/raptor_progress` - Get RAPTOR status

#### Document Management (`api/apps/document_app.py`)
- `POST /api/v1/document/upload` - Upload documents
- `POST /api/v1/document/update` - Update document
- `GET /api/v1/document/download` - Download document
- `POST /api/v1/document/list` - List documents
- `POST /api/v1/document/rm` - Delete documents
- `POST /api/v1/document/run` - Parse documents
- `POST /api/v1/document/stop` - Stop parsing

#### Chunk Management (`api/apps/chunk_app.py`)
- `POST /api/v1/chunk/create` - Add chunk
- `POST /api/v1/chunk/list` - List chunks
- `POST /api/v1/chunk/rm` - Delete chunks
- `POST /api/v1/chunk/update` - Update chunk
- `POST /api/v1/chunk/retrieval_test` - Retrieve chunks

#### Chat Assistant Management (`api/apps/dialog_app.py`)
- `POST /api/v1/dialog/set` - Create/Update chat assistant
- `GET /api/v1/dialog/get` - Get chat assistant
- `GET /api/v1/dialog/list` - List chat assistants
- `POST /api/v1/dialog/rm` - Delete chat assistants

#### Session Management (`api/apps/conversation_app.py`)
- `POST /api/v1/conversation/set` - Create/Update session
- `GET /api/v1/conversation/get` - Get session
- `GET /api/v1/conversation/list` - List sessions
- `POST /api/v1/conversation/rm` - Delete sessions
- `POST /api/v1/dialog/next` - Converse with assistant

#### User & Auth (`api/apps/user_app.py`)
- `POST /api/v1/user/register` - Register new user
- `POST /api/v1/user/login` - Login
- `GET /api/v1/user/info` - Get user info
- `POST /api/v1/user/logout` - Logout

#### LLM Configuration (`api/apps/llm_app.py`) - Modified
- `GET /api/v1/llm/factories` - List factories (only HuggingFace, OpenRouter)
- `POST /api/v1/llm/set_api_key` - Set API key
- `GET /api/v1/llm/my_llms` - Get user's configured LLMs

### 2.2 NEW API Endpoints for RBAC

Create new file `api/apps/rbac_app.py`:

#### Group Management
- `POST /api/v1/group/create` - Create user group (admin only)
- `PUT /api/v1/group/<group_id>` - Update group (admin only)
- `DELETE /api/v1/group/<group_id>` - Delete group (admin only)
- `GET /api/v1/group/list` - List all groups (admin) or user's groups

#### Group Membership
- `POST /api/v1/group/<group_id>/member` - Add user to group (admin only)
- `DELETE /api/v1/group/<group_id>/member/<user_id>` - Remove user (admin only)
- `GET /api/v1/group/<group_id>/members` - List group members

#### Knowledge Base Permissions
- `POST /api/v1/permission/kb` - Set group permissions on KB (admin only)
- `PUT /api/v1/permission/kb/<permission_id>` - Update permission (admin only)
- `DELETE /api/v1/permission/kb/<permission_id>` - Remove permission (admin only)
- `GET /api/v1/permission/kb/<kb_id>` - Get permissions for KB
- `GET /api/v1/permission/my` - Get current user's permissions

#### User Management (Admin)
- `GET /api/v1/admin/users` - List all users (admin only)
- `PUT /api/v1/admin/user/<user_id>` - Update user (admin only)
- `DELETE /api/v1/admin/user/<user_id>` - Delete user (admin only)

### 2.3 API Endpoints to REMOVE

Delete or disable these files/endpoints:
- `api/apps/canvas_app.py` - Agent canvas (entire file)
- `api/apps/search_app.py` - Search functionality (entire file)
- `api/apps/connector_app.py` - Data connectors (entire file)
- `api/apps/mcp_server_app.py` - MCP servers (entire file)
- `api/apps/evaluation_app.py` - Evaluation (entire file)
- `api/apps/langfuse_app.py` - Langfuse integration (entire file)
- `api/apps/plugin_app.py` - Plugins (entire file)
- `api/apps/file_app.py` - File management (entire file)
- `api/apps/file2document_app.py` - File mapping (entire file)
- `api/apps/tenant_app.py` - Tenant management (replaced by RBAC)

### 2.4 Service Layer Changes

Create new services in `api/db/services/`:

```
rbac_service.py:
- UserGroupService
- UserGroupMemberService
- GroupKnowledgebasePermissionService
- PermissionChecker (utility class)
```

Modify existing services to use RBAC:
- `knowledgebase_service.py` - Add permission checks
- `document_service.py` - Add permission checks
- `dialog_service.py` - Add permission checks for KB access
- `conversation_service.py` - Add permission checks

---

## Phase 3: Permission Enforcement

### 3.1 Permission Decorator

Create `api/utils/rbac.py`:

```python
def require_permission(resource_type: str, permission: str):
    """
    Decorator to check permissions before endpoint execution.

    Usage:
    @require_permission('kb', 'read')
    async def get_kb(kb_id): ...
    """

def require_admin():
    """Decorator to require admin group membership"""

def get_user_kb_permissions(user_id: str, kb_id: str) -> dict:
    """Get user's effective permissions on a KB through all their groups"""
```

### 3.2 Permission Checks by Endpoint

| Endpoint | Permission Required |
|----------|-------------------|
| List datasets | read (shows only accessible KBs) |
| Create dataset | Admin only |
| Update dataset | update on specific KB |
| Delete dataset | delete on specific KB |
| Upload document | create on KB |
| Update document | update on KB |
| Delete document | delete on KB |
| List documents | read on KB |
| Parse documents | create on KB |
| Add chunk | create on KB |
| Update chunk | update on KB |
| Delete chunk | delete on KB |
| List chunks | read on KB |
| Retrieve chunks | read on KB |
| Create chat assistant | Must have read on all attached KBs |
| Update chat assistant | Same as create |
| Use chat assistant | Must have read on all attached KBs |
| Create/manage groups | Admin only |
| Manage permissions | Admin only |

### 3.3 Registration Flow

1. User registers via `/api/v1/user/register`
2. System creates user record
3. System adds user to default "Users" group
4. User has no KB access until admin assigns permissions
5. Admin can promote user to "Administrators" group for full access

---

## Phase 4: LLM Provider Cleanup

### 4.1 Backend Files to Modify

#### `rag/llm/__init__.py`
- Remove all providers from `SupportedLiteLLMProvider` except OpenRouter
- Update factory registration to only include HuggingFace, OpenRouter

#### `rag/llm/chat_model.py`
- Keep: `Base`, `LiteLLMBase` (for OpenRouter), `HuggingFaceChat`
- Remove: All other provider classes (~18 classes)

#### `rag/llm/embedding_model.py`
- Keep: `Base`, `HuggingFaceEmbed`, `OpenRouterEmbed` (if exists, else create)
- Remove: All other embedding classes (~30 classes)

#### `rag/llm/rerank_model.py`
- Keep: `Base`, `HuggingfaceRerank`
- Remove: All other rerank classes (~15 classes)

#### `rag/llm/cv_model.py`
- Keep: `Base`, `OpenRouterChat` (for vision)
- Remove: All other vision classes (~20 classes)

#### `rag/llm/tts_model.py`
- Keep: `Base`, minimal TTS if needed
- Remove: Most TTS implementations

#### `rag/llm/sequence2txt_model.py`
- Keep: `Base`, minimal ASR if needed
- Remove: Most ASR implementations

### 4.2 Configuration Files

#### `conf/llm_factories.json`
Keep only entries for:
- HuggingFace
- OpenRouter

Remove all other factory definitions (~65 entries)

### 4.3 Dependencies

Review `pyproject.toml` and remove unused provider SDKs:
- Remove: `anthropic`, `cohere`, `dashscope`, `zhipuai`, `qianfan`, `volcengine`, etc.
- Keep: `huggingface-hub`, `litellm` (for OpenRouter)

---

## Phase 5: Frontend Refactoring

### 5.1 Routes to KEEP

```typescript
// Auth
'/login-next'
'/logout'

// Home/Dashboard
'/'
'/home'

// Knowledge Base
'/datasets'
'/dataset/:id'
'/dataset/overview/:id'
'/dataset/setting/:id'
'/dataset/knowledge-graph/:id'
'/dataset/testing/:id'

// Chat
'/next-chats'
'/next-chats/chat/:id'

// Document/Chunk
'/chunk'
'/chunk/chunk/:id'
'/document/:id'

// User Settings (modified)
'/user-setting'
'/user-setting/profile'
'/user-setting/locale'
'/user-setting/model'  // Only HuggingFace/OpenRouter

// NEW: Admin/RBAC
'/admin'
'/admin/users'
'/admin/groups'
'/admin/permissions'
```

### 5.2 Routes to REMOVE

```typescript
// Remove these routes
'/agents'
'/agent/:id'
'/agent/share'
'/agent-templates'
'/agent-log-page/:id'
'/next-searches'
'/next-search/:id'
'/files'
'/user-setting/team'  // Replaced by groups
'/user-setting/api'   // Simplified
'/user-setting/mcp'   // MCP removed
'/user-setting/data-source'  // Connectors removed
'/dataflow-result'
'/next-chats/share'   // Optional: remove if sharing not needed
'/next-chats/widget'  // Optional: remove if widget not needed
```

### 5.3 Pages to DELETE

```
web/src/pages/agents/
web/src/pages/agent/
web/src/pages/next-searches/
web/src/pages/next-search/
web/src/pages/files/
web/src/pages/dataflow-result/
web/src/pages/user-setting/mcp/
web/src/pages/user-setting/data-source/
web/src/pages/user-setting/setting-team/  (replace with groups)
```

### 5.4 New Pages to CREATE

```
web/src/pages/admin/
  ├── index.tsx          # Admin dashboard
  ├── users.tsx          # User management
  ├── groups.tsx         # Group management
  ├── group-detail.tsx   # Group members & permissions
  └── permissions.tsx    # KB permission matrix
```

### 5.5 Services to Modify

#### `web/src/services/knowledge-service.ts`
- Keep all KB, document, chunk methods
- Add permission check responses handling

#### `web/src/services/user-service.ts`
- Keep auth methods
- Add group/permission API calls

#### NEW: `web/src/services/rbac-service.ts`
```typescript
// Group management
createGroup(data)
updateGroup(groupId, data)
deleteGroup(groupId)
listGroups()

// Membership
addGroupMember(groupId, userId)
removeGroupMember(groupId, userId)
listGroupMembers(groupId)

// Permissions
setKbPermission(data)
updateKbPermission(permissionId, data)
deleteKbPermission(permissionId)
getKbPermissions(kbId)
getMyPermissions()
```

### 5.6 Services to DELETE

```
web/src/services/agent-service.ts
web/src/services/search-service.ts
web/src/services/file-manager-service.ts
web/src/services/data-source-service.ts
web/src/services/mcp-server-service.ts
web/src/services/plugin-service.ts
```

### 5.7 LLM Constants Update

#### `web/src/constants/llm.ts`
```typescript
export enum LLMFactory {
  HuggingFace = 'HuggingFace',
  OpenRouter = 'OpenRouter',
}

// Remove all other enum values (~62 entries)
```

### 5.8 Model Settings Page

Modify `web/src/pages/user-setting/setting-model/`:
- Keep only HuggingFace and OpenRouter configuration modals
- Delete all other provider-specific modals (11 directories)
- Simplify the factory selection UI

### 5.9 Permission-Aware Components

Update components to respect permissions:

```typescript
// Example: Dataset list should filter by readable KBs
const { data: datasets } = useDatasets();
// Backend already filters, but UI should handle empty states

// Example: Hide edit button if no update permission
{hasPermission(kb.id, 'update') && <EditButton />}

// Example: Disable chat if no read permission on attached KBs
{canUseChat(dialog.kb_ids) && <ChatButton />}
```

### 5.10 State Management Updates

Update Zustand stores:
- Remove agent-related stores
- Add permission state to user store
- Add admin state for group management

---

## Phase 6: Implementation Order

### Step 1: Database & Models (Day 1-2)
1. Add new RBAC models to `db_models.py`
2. Create migration script
3. Test database changes

### Step 2: RBAC Services (Day 2-3)
1. Create `rbac_service.py`
2. Implement permission checker utility
3. Create RBAC decorators

### Step 3: RBAC API Endpoints (Day 3-4)
1. Create `rbac_app.py` with all group/permission endpoints
2. Register blueprint in `__init__.py`
3. Test endpoints

### Step 4: Modify Existing APIs (Day 4-6)
1. Add permission checks to KB endpoints
2. Add permission checks to document endpoints
3. Add permission checks to chunk endpoints
4. Add permission checks to dialog/conversation endpoints
5. Modify registration to add default group

### Step 5: Remove Unused Backend (Day 6-7)
1. Remove unused API app files
2. Remove unused services
3. Clean up imports and registrations

### Step 6: LLM Provider Cleanup (Day 7-8)
1. Modify `rag/llm/` files to keep only HuggingFace/OpenRouter
2. Update `llm_factories.json`
3. Update dependencies in `pyproject.toml`

### Step 7: Frontend Route Cleanup (Day 8-9)
1. Remove unused routes from `routes.ts`
2. Delete unused page directories
3. Delete unused service files

### Step 8: Frontend RBAC Pages (Day 9-11)
1. Create admin pages for user/group management
2. Create permission management UI
3. Add RBAC service

### Step 9: Frontend Permission Integration (Day 11-12)
1. Update components to check permissions
2. Hide/disable UI elements based on permissions
3. Handle permission errors gracefully

### Step 10: Frontend LLM Cleanup (Day 12-13)
1. Update LLM constants
2. Remove provider-specific modals
3. Simplify model settings page

### Step 11: Testing & Polish (Day 13-15)
1. End-to-end testing of all flows
2. Permission testing (positive and negative cases)
3. UI/UX polish
4. Documentation update

---

## File Change Summary

### Backend Files to CREATE
- `api/apps/rbac_app.py`
- `api/db/services/rbac_service.py`
- `api/utils/rbac.py`
- `migrations/add_rbac_tables.py`

### Backend Files to MODIFY
- `api/db/db_models.py` (add RBAC models)
- `api/apps/__init__.py` (register new blueprint, remove old ones)
- `api/apps/kb_app.py` (add permission checks)
- `api/apps/document_app.py` (add permission checks)
- `api/apps/chunk_app.py` (add permission checks)
- `api/apps/dialog_app.py` (add permission checks)
- `api/apps/conversation_app.py` (add permission checks)
- `api/apps/user_app.py` (add default group on registration)
- `api/apps/llm_app.py` (filter to HuggingFace/OpenRouter only)
- `rag/llm/__init__.py`
- `rag/llm/chat_model.py`
- `rag/llm/embedding_model.py`
- `rag/llm/rerank_model.py`
- `rag/llm/cv_model.py`
- `rag/llm/tts_model.py`
- `rag/llm/sequence2txt_model.py`
- `conf/llm_factories.json`
- `pyproject.toml`

### Backend Files to DELETE
- `api/apps/canvas_app.py`
- `api/apps/search_app.py`
- `api/apps/connector_app.py`
- `api/apps/mcp_server_app.py`
- `api/apps/evaluation_app.py`
- `api/apps/langfuse_app.py`
- `api/apps/plugin_app.py`
- `api/apps/file_app.py`
- `api/apps/file2document_app.py`
- `api/apps/tenant_app.py`
- `api/db/services/canvas_service.py`
- `api/db/services/search_service.py`
- `api/db/services/connector_service.py`
- `api/db/services/mcp_server_service.py`
- `api/db/services/evaluation_service.py`
- `api/db/services/langfuse_service.py`

### Frontend Files to CREATE
- `web/src/pages/admin/index.tsx`
- `web/src/pages/admin/users.tsx`
- `web/src/pages/admin/groups.tsx`
- `web/src/pages/admin/group-detail.tsx`
- `web/src/pages/admin/permissions.tsx`
- `web/src/services/rbac-service.ts`
- `web/src/hooks/use-rbac.ts`

### Frontend Files to MODIFY
- `web/src/routes.ts`
- `web/src/constants/llm.ts`
- `web/src/services/user-service.ts`
- `web/src/services/knowledge-service.ts`
- `web/src/pages/user-setting/setting-model/index.tsx`
- `web/src/pages/datasets/index.tsx` (permission-aware)
- `web/src/pages/dataset/*` (permission-aware)
- `web/src/pages/next-chats/*` (permission-aware)
- `web/src/layouts/next-header.tsx` (remove menu items)
- `web/src/pages/home/*` (remove agent/search widgets)

### Frontend Directories to DELETE
- `web/src/pages/agents/`
- `web/src/pages/agent/`
- `web/src/pages/next-searches/`
- `web/src/pages/next-search/`
- `web/src/pages/files/`
- `web/src/pages/dataflow-result/`
- `web/src/pages/user-setting/mcp/`
- `web/src/pages/user-setting/data-source/`
- `web/src/pages/user-setting/setting-team/`
- `web/src/pages/user-setting/setting-model/modal/azure-openai-modal/`
- `web/src/pages/user-setting/setting-model/modal/bedrock-modal/`
- `web/src/pages/user-setting/setting-model/modal/fish-audio-modal/`
- `web/src/pages/user-setting/setting-model/modal/google-modal/`
- `web/src/pages/user-setting/setting-model/modal/hunyuan-modal/`
- `web/src/pages/user-setting/setting-model/modal/next-tencent-modal/`
- `web/src/pages/user-setting/setting-model/modal/ollama-modal/`
- `web/src/pages/user-setting/setting-model/modal/spark-modal/`
- `web/src/pages/user-setting/setting-model/modal/volcengine-modal/`
- `web/src/pages/user-setting/setting-model/modal/yiyan-modal/`
- `web/src/services/agent-service.ts`
- `web/src/services/search-service.ts`
- `web/src/services/file-manager-service.ts`
- `web/src/services/data-source-service.ts`
- `web/src/services/mcp-server-service.ts`
- `web/src/services/plugin-service.ts`

---

## API Summary

### Final API Endpoint List

#### Authentication
- `POST /api/v1/user/register`
- `POST /api/v1/user/login`
- `POST /api/v1/user/logout`
- `GET /api/v1/user/info`

#### Dataset Management
- `POST /api/v1/kb/create`
- `POST /api/v1/kb/update`
- `POST /api/v1/kb/rm`
- `POST /api/v1/kb/list`
- `GET /api/v1/kb/<kb_id>/knowledge_graph`
- `DELETE /api/v1/kb/<kb_id>/knowledge_graph`
- `POST /api/v1/kb/run_graphrag`
- `GET /api/v1/kb/graphrag_progress`
- `POST /api/v1/kb/run_raptor`
- `GET /api/v1/kb/raptor_progress`

#### Document Management
- `POST /api/v1/document/upload`
- `POST /api/v1/document/update`
- `GET /api/v1/document/download`
- `POST /api/v1/document/list`
- `POST /api/v1/document/rm`
- `POST /api/v1/document/run`
- `POST /api/v1/document/stop`

#### Chunk Management
- `POST /api/v1/chunk/create`
- `POST /api/v1/chunk/list`
- `POST /api/v1/chunk/rm`
- `POST /api/v1/chunk/update`
- `POST /api/v1/chunk/retrieval_test`

#### Chat Assistant
- `POST /api/v1/dialog/set`
- `GET /api/v1/dialog/get`
- `GET /api/v1/dialog/list`
- `POST /api/v1/dialog/rm`

#### Session/Conversation
- `POST /api/v1/conversation/set`
- `GET /api/v1/conversation/get`
- `GET /api/v1/conversation/list`
- `POST /api/v1/conversation/rm`
- `POST /api/v1/dialog/next`

#### RBAC - Groups
- `POST /api/v1/group/create`
- `PUT /api/v1/group/<group_id>`
- `DELETE /api/v1/group/<group_id>`
- `GET /api/v1/group/list`
- `POST /api/v1/group/<group_id>/member`
- `DELETE /api/v1/group/<group_id>/member/<user_id>`
- `GET /api/v1/group/<group_id>/members`

#### RBAC - Permissions
- `POST /api/v1/permission/kb`
- `PUT /api/v1/permission/kb/<permission_id>`
- `DELETE /api/v1/permission/kb/<permission_id>`
- `GET /api/v1/permission/kb/<kb_id>`
- `GET /api/v1/permission/my`

#### Admin
- `GET /api/v1/admin/users`
- `PUT /api/v1/admin/user/<user_id>`
- `DELETE /api/v1/admin/user/<user_id>`

#### LLM
- `GET /api/v1/llm/factories`
- `POST /api/v1/llm/set_api_key`
- `GET /api/v1/llm/my_llms`

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing deployments | Create migration script, document upgrade path |
| Permission bugs allowing unauthorized access | Comprehensive permission tests, default deny |
| Frontend/Backend API mismatch | Generate TypeScript types from backend |
| Lost functionality users depend on | Document removed features, provide alternatives |
| LLM integration issues after cleanup | Keep litellm for OpenRouter compatibility |

---

## Success Criteria

1. ✅ Only specified API endpoints are available
2. ✅ RBAC system fully functional with groups and permissions
3. ✅ User registration creates user in default group
4. ✅ Admin users can manage all resources
5. ✅ Non-admin users can only access permitted KBs
6. ✅ Chat assistants respect KB permissions
7. ✅ Only HuggingFace and OpenRouter LLM providers available
8. ✅ Frontend reflects all backend changes
9. ✅ All tests pass
10. ✅ No unauthorized access possible
