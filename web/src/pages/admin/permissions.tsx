import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { LucidePlus, LucideSearch, LucideTrash2, LucideEdit } from 'lucide-react';

import Spotlight from '@/components/spotlight';
import { TableEmpty } from '@/components/table-skeleton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RAGFlowPagination } from '@/components/ui/ragflow-pagination';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

import {
  listGroupsApi,
  setKbPermissionApi,
  updateKbPermissionApi,
  deleteKbPermissionApi,
  getKbPermissionsApi,
  UserGroup,
  KbPermission,
} from '@/services/rbac-service';
import { listKnowledgeBase } from '@/services/knowledge-service';

import { createFuzzySearchFn, EMPTY_DATA } from './utils';

interface PermissionRow {
  id: string;
  group_id: string;
  group_name: string;
  kb_id: string;
  kb_name: string;
  can_read: boolean;
  can_update: boolean;
  can_delete: boolean;
  can_create: boolean;
}

const columnHelper = createColumnHelper<PermissionRow>();
const globalFilterFn = createFuzzySearchFn<PermissionRow>([
  'group_name',
  'kb_name',
]);

function AdminPermissions() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedPermission, setSelectedPermission] =
    useState<PermissionRow | null>(null);
  const [selectedKbId, setSelectedKbId] = useState<string>('');

  // Form state
  const [formGroupId, setFormGroupId] = useState('');
  const [formKbId, setFormKbId] = useState('');
  const [canRead, setCanRead] = useState(false);
  const [canUpdate, setCanUpdate] = useState(false);
  const [canDelete, setCanDelete] = useState(false);
  const [canCreate, setCanCreate] = useState(false);

  // Query groups
  const { data: groupsList } = useQuery({
    queryKey: ['admin/listGroups'],
    queryFn: async () => {
      const res = await listGroupsApi();
      return (res?.data?.data || []) as UserGroup[];
    },
    retry: false,
  });

  // Query knowledge bases
  const { data: kbList } = useQuery({
    queryKey: ['admin/listKnowledgeBases'],
    queryFn: async () => {
      const res = await listKnowledgeBase({ page: 1, page_size: 1000 });
      return res?.data?.kbs || [];
    },
    retry: false,
  });

  // Query permissions for selected KB
  const { data: permissionsList } = useQuery({
    queryKey: ['admin/kbPermissions', selectedKbId],
    queryFn: async () => {
      if (!selectedKbId) return [];
      const res = await getKbPermissionsApi(selectedKbId);
      return (res?.data?.data || []) as PermissionRow[];
    },
    enabled: !!selectedKbId,
    retry: false,
  });

  // Create permission mutation
  const createPermissionMutation = useMutation({
    mutationFn: setKbPermissionApi,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['admin/kbPermissions', selectedKbId],
      });
      setCreateModalOpen(false);
      resetForm();
    },
    retry: false,
  });

  // Update permission mutation
  const updatePermissionMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      updateKbPermissionApi(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['admin/kbPermissions', selectedKbId],
      });
      setEditModalOpen(false);
      resetForm();
    },
    retry: false,
  });

  // Delete permission mutation
  const deletePermissionMutation = useMutation({
    mutationFn: deleteKbPermissionApi,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['admin/kbPermissions', selectedKbId],
      });
      setDeleteModalOpen(false);
      setSelectedPermission(null);
    },
    retry: false,
  });

  const resetForm = () => {
    setFormGroupId('');
    setFormKbId('');
    setCanRead(false);
    setCanUpdate(false);
    setCanDelete(false);
    setCanCreate(false);
    setSelectedPermission(null);
  };

  const openEditModal = (permission: PermissionRow) => {
    setSelectedPermission(permission);
    setFormGroupId(permission.group_id);
    setFormKbId(permission.kb_id);
    setCanRead(permission.can_read);
    setCanUpdate(permission.can_update);
    setCanDelete(permission.can_delete);
    setCanCreate(permission.can_create);
    setEditModalOpen(true);
  };

  const openCreateModal = () => {
    setFormKbId(selectedKbId);
    setCreateModalOpen(true);
  };

  const columnDefs = useMemo(
    () => [
      columnHelper.accessor('group_name', {
        header: t('admin.group'),
        cell: ({ cell }) => (
          <span className="font-medium">{cell.getValue()}</span>
        ),
      }),
      columnHelper.accessor('can_read', {
        header: t('admin.canRead'),
        cell: ({ cell }) =>
          cell.getValue() ? (
            <Badge variant="success">{t('admin.yes')}</Badge>
          ) : (
            <Badge variant="secondary">{t('admin.no')}</Badge>
          ),
      }),
      columnHelper.accessor('can_create', {
        header: t('admin.canCreate'),
        cell: ({ cell }) =>
          cell.getValue() ? (
            <Badge variant="success">{t('admin.yes')}</Badge>
          ) : (
            <Badge variant="secondary">{t('admin.no')}</Badge>
          ),
      }),
      columnHelper.accessor('can_update', {
        header: t('admin.canUpdate'),
        cell: ({ cell }) =>
          cell.getValue() ? (
            <Badge variant="success">{t('admin.yes')}</Badge>
          ) : (
            <Badge variant="secondary">{t('admin.no')}</Badge>
          ),
      }),
      columnHelper.accessor('can_delete', {
        header: t('admin.canDelete'),
        cell: ({ cell }) =>
          cell.getValue() ? (
            <Badge variant="success">{t('admin.yes')}</Badge>
          ) : (
            <Badge variant="secondary">{t('admin.no')}</Badge>
          ),
      }),
      columnHelper.display({
        id: 'actions',
        header: t('admin.actions'),
        cell: ({ row }) => (
          <div className="opacity-0 group-hover/row:opacity-100 group-focus-within/row:opacity-100 transition-opacity flex gap-1">
            <Button
              variant="transparent"
              size="icon"
              className="border-0"
              onClick={() => openEditModal(row.original)}
            >
              <LucideEdit />
            </Button>
            <Button
              variant="danger"
              size="icon"
              className="border-0"
              onClick={() => {
                setSelectedPermission(row.original);
                setDeleteModalOpen(true);
              }}
            >
              <LucideTrash2 />
            </Button>
          </div>
        ),
      }),
    ],
    [t],
  );

  const table = useReactTable({
    data: permissionsList ?? EMPTY_DATA,
    columns: columnDefs,
    globalFilterFn,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  // Get groups not already having permission for selected KB
  const availableGroups = useMemo(() => {
    if (!groupsList || !permissionsList) return groupsList || [];
    const existingGroupIds = new Set(
      (permissionsList as PermissionRow[]).map((p) => p.group_id),
    );
    return groupsList.filter((g: UserGroup) => !existingGroupIds.has(g.id));
  }, [groupsList, permissionsList]);

  return (
    <>
      <Card className="!shadow-none relative h-full bg-transparent overflow-hidden">
        <Spotlight />

        <ScrollArea className="size-full">
          <CardHeader className="space-y-0 flex flex-row justify-between items-center">
            <CardTitle>{t('admin.permissionManagement')}</CardTitle>

            <div className="ml-auto flex justify-end gap-4">
              <Select value={selectedKbId} onValueChange={setSelectedKbId}>
                <SelectTrigger className="w-64 h-10 bg-bg-input border-border-button">
                  <SelectValue placeholder={t('admin.selectKnowledgeBase')} />
                </SelectTrigger>
                <SelectContent>
                  {kbList?.map((kb: any) => (
                    <SelectItem key={kb.id} value={kb.id}>
                      {kb.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <div className="relative w-56">
                <LucideSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <Input
                  className="pl-10 h-10 bg-bg-input border-border-button"
                  placeholder={t('header.search')}
                  value={table.getState().globalFilter}
                  onChange={(e) => table.setGlobalFilter(e.target.value)}
                />
              </div>

              <Button
                className="h-10 px-4"
                onClick={openCreateModal}
                disabled={!selectedKbId}
              >
                <LucidePlus />
                {t('admin.addPermission')}
              </Button>
            </div>
          </CardHeader>

          <CardContent>
            {!selectedKbId ? (
              <div className="text-center py-16 text-text-secondary">
                {t('admin.selectKnowledgeBasePrompt')}
              </div>
            ) : (
              <Table>
                <colgroup>
                  <col className="w-[25%]" />
                  <col className="w-[12%]" />
                  <col className="w-[12%]" />
                  <col className="w-[12%]" />
                  <col className="w-[12%]" />
                  <col className="w-[20%]" />
                </colgroup>

                <TableHeader>
                  {table.getHeaderGroups().map((headerGroup) => (
                    <TableRow key={headerGroup.id}>
                      {headerGroup.headers.map((header) => (
                        <TableHead key={header.id}>
                          {header.isPlaceholder
                            ? null
                            : flexRender(
                                header.column.columnDef.header,
                                header.getContext(),
                              )}
                        </TableHead>
                      ))}
                    </TableRow>
                  ))}
                </TableHeader>

                <TableBody>
                  {table.getRowModel().rows?.length ? (
                    table.getRowModel().rows.map((row) => (
                      <TableRow key={row.id} className="group/row">
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id}>
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))
                  ) : (
                    <TableEmpty key="empty" columnsLength={columnDefs.length} />
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>

          <CardFooter className="flex items-center justify-end">
            <RAGFlowPagination
              total={permissionsList?.length ?? 0}
              current={table.getState().pagination.pageIndex + 1}
              pageSize={table.getState().pagination.pageSize}
              onChange={(page, pageSize) => {
                table.setPagination({
                  pageIndex: page - 1,
                  pageSize,
                });
              }}
            />
          </CardFooter>
        </ScrollArea>
      </Card>

      {/* Create Permission Modal */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.addPermission')}</DialogTitle>
          </DialogHeader>

          <section className="px-6 space-y-4">
            <div>
              <Label>{t('admin.group')}</Label>
              <Select value={formGroupId} onValueChange={setFormGroupId}>
                <SelectTrigger className="bg-bg-input border-border-button">
                  <SelectValue placeholder={t('admin.selectGroup')} />
                </SelectTrigger>
                <SelectContent>
                  {availableGroups?.map((group: UserGroup) => (
                    <SelectItem key={group.id} value={group.id}>
                      {group.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <Label>{t('admin.permissions')}</Label>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center gap-2">
                  <Switch checked={canRead} onCheckedChange={setCanRead} />
                  <Label>{t('admin.canRead')}</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={canCreate} onCheckedChange={setCanCreate} />
                  <Label>{t('admin.canCreate')}</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={canUpdate} onCheckedChange={setCanUpdate} />
                  <Label>{t('admin.canUpdate')}</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={canDelete} onCheckedChange={setCanDelete} />
                  <Label>{t('admin.canDelete')}</Label>
                </div>
              </div>
            </div>
          </section>

          <DialogFooter className="gap-4 px-6 py-4">
            <Button
              variant="outline"
              onClick={() => {
                setCreateModalOpen(false);
                resetForm();
              }}
            >
              {t('admin.cancel')}
            </Button>
            <Button
              onClick={() =>
                createPermissionMutation.mutate({
                  group_id: formGroupId,
                  kb_id: selectedKbId,
                  can_read: canRead,
                  can_update: canUpdate,
                  can_delete: canDelete,
                  can_create: canCreate,
                })
              }
              disabled={!formGroupId || createPermissionMutation.isPending}
              loading={createPermissionMutation.isPending}
            >
              {t('admin.create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Permission Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.editPermission')}</DialogTitle>
          </DialogHeader>

          <section className="px-6 space-y-4">
            <div>
              <Label>{t('admin.group')}</Label>
              <Input
                value={selectedPermission?.group_name || ''}
                disabled
                className="bg-bg-input"
              />
            </div>

            <div className="space-y-3">
              <Label>{t('admin.permissions')}</Label>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center gap-2">
                  <Switch checked={canRead} onCheckedChange={setCanRead} />
                  <Label>{t('admin.canRead')}</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={canCreate} onCheckedChange={setCanCreate} />
                  <Label>{t('admin.canCreate')}</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={canUpdate} onCheckedChange={setCanUpdate} />
                  <Label>{t('admin.canUpdate')}</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={canDelete} onCheckedChange={setCanDelete} />
                  <Label>{t('admin.canDelete')}</Label>
                </div>
              </div>
            </div>
          </section>

          <DialogFooter className="gap-4 px-6 py-4">
            <Button
              variant="outline"
              onClick={() => {
                setEditModalOpen(false);
                resetForm();
              }}
            >
              {t('admin.cancel')}
            </Button>
            <Button
              onClick={() =>
                selectedPermission &&
                updatePermissionMutation.mutate({
                  id: selectedPermission.id,
                  data: {
                    can_read: canRead,
                    can_update: canUpdate,
                    can_delete: canDelete,
                    can_create: canCreate,
                  },
                })
              }
              disabled={updatePermissionMutation.isPending}
              loading={updatePermissionMutation.isPending}
            >
              {t('admin.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Permission Modal */}
      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.deletePermission')}</DialogTitle>
          </DialogHeader>

          <section className="px-6">
            <DialogDescription>
              {t('admin.deletePermissionConfirmation')}
            </DialogDescription>
            <div className="rounded-lg mt-6 p-4 border-0.5 border-border-button">
              {selectedPermission?.group_name}
            </div>
          </section>

          <DialogFooter className="gap-4 px-6 py-4">
            <Button variant="outline" onClick={() => setDeleteModalOpen(false)}>
              {t('admin.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() =>
                selectedPermission &&
                deletePermissionMutation.mutate(selectedPermission.id)
              }
              disabled={deletePermissionMutation.isPending}
              loading={deletePermissionMutation.isPending}
            >
              {t('admin.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default AdminPermissions;
