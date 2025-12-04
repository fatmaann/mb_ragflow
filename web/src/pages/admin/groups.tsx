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

import {
  LucidePlus,
  LucideSearch,
  LucideTrash2,
  LucideUserPlus,
  LucideEdit,
} from 'lucide-react';

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
import { Textarea } from '@/components/ui/textarea';
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
  createGroupApi,
  updateGroupApi,
  deleteGroupApi,
  listGroupMembersApi,
  addGroupMemberApi,
  removeGroupMemberApi,
  UserGroup,
  GroupMember,
} from '@/services/rbac-service';
import { listUsers } from '@/services/admin-service';

import { createFuzzySearchFn, EMPTY_DATA } from './utils';

const columnHelper = createColumnHelper<UserGroup>();
const globalFilterFn = createFuzzySearchFn<UserGroup>(['name', 'description']);

function AdminGroups() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [membersModalOpen, setMembersModalOpen] = useState(false);
  const [addMemberModalOpen, setAddMemberModalOpen] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<UserGroup | null>(null);

  // Form state
  const [groupName, setGroupName] = useState('');
  const [groupDescription, setGroupDescription] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);

  // Query groups
  const { data: groupsList } = useQuery({
    queryKey: ['admin/listGroups'],
    queryFn: async () => {
      const res = await listGroupsApi();
      return res?.data?.data || [];
    },
    retry: false,
  });

  // Query group members
  const { data: groupMembers } = useQuery({
    queryKey: ['admin/groupMembers', selectedGroup?.id],
    queryFn: async () => {
      if (!selectedGroup?.id) return [];
      const res = await listGroupMembersApi(selectedGroup.id);
      return res?.data?.data || [];
    },
    enabled: !!selectedGroup?.id && membersModalOpen,
    retry: false,
  });

  // Query all users for adding members
  const { data: allUsers } = useQuery({
    queryKey: ['admin/listUsers'],
    queryFn: async () => (await listUsers()).data.data,
    enabled: addMemberModalOpen,
    retry: false,
  });

  // Create group mutation
  const createGroupMutation = useMutation({
    mutationFn: createGroupApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin/listGroups'] });
      setCreateModalOpen(false);
      resetForm();
    },
    retry: false,
  });

  // Update group mutation
  const updateGroupMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      updateGroupApi(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin/listGroups'] });
      setEditModalOpen(false);
      resetForm();
    },
    retry: false,
  });

  // Delete group mutation
  const deleteGroupMutation = useMutation({
    mutationFn: deleteGroupApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin/listGroups'] });
      setDeleteModalOpen(false);
      setSelectedGroup(null);
    },
    retry: false,
  });

  // Add member mutation
  const addMemberMutation = useMutation({
    mutationFn: ({ groupId, userId }: { groupId: string; userId: string }) =>
      addGroupMemberApi(groupId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['admin/groupMembers', selectedGroup?.id],
      });
      setAddMemberModalOpen(false);
    },
    retry: false,
  });

  // Remove member mutation
  const removeMemberMutation = useMutation({
    mutationFn: ({ groupId, userId }: { groupId: string; userId: string }) =>
      removeGroupMemberApi(groupId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['admin/groupMembers', selectedGroup?.id],
      });
    },
    retry: false,
  });

  const resetForm = () => {
    setGroupName('');
    setGroupDescription('');
    setIsAdmin(false);
    setSelectedGroup(null);
  };

  const openEditModal = (group: UserGroup) => {
    setSelectedGroup(group);
    setGroupName(group.name);
    setGroupDescription(group.description || '');
    setIsAdmin(group.is_admin);
    setEditModalOpen(true);
  };

  const columnDefs = useMemo(
    () => [
      columnHelper.accessor('name', {
        header: t('admin.groupName'),
        cell: ({ cell }) => (
          <span className="font-medium">{cell.getValue()}</span>
        ),
      }),
      columnHelper.accessor('description', {
        header: t('admin.description'),
        cell: ({ cell }) => (
          <span className="text-text-secondary">{cell.getValue() || '-'}</span>
        ),
      }),
      columnHelper.accessor('is_admin', {
        header: t('admin.adminGroup'),
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
              onClick={() => {
                setSelectedGroup(row.original);
                setMembersModalOpen(true);
              }}
            >
              <LucideUserPlus />
            </Button>
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
                setSelectedGroup(row.original);
                setDeleteModalOpen(true);
              }}
              disabled={
                row.original.name === 'Administrators' ||
                row.original.name === 'Users'
              }
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
    data: groupsList ?? EMPTY_DATA,
    columns: columnDefs,
    globalFilterFn,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  // Get users not already in the group
  const availableUsers = useMemo(() => {
    if (!allUsers || !groupMembers) return [];
    const memberIds = new Set(
      (groupMembers as GroupMember[]).map((m) => m.user_id),
    );
    return allUsers.filter(
      (user: AdminService.ListUsersItem) => !memberIds.has(user.id),
    );
  }, [allUsers, groupMembers]);

  return (
    <>
      <Card className="!shadow-none relative h-full bg-transparent overflow-hidden">
        <Spotlight />

        <ScrollArea className="size-full">
          <CardHeader className="space-y-0 flex flex-row justify-between items-center">
            <CardTitle>{t('admin.groupManagement')}</CardTitle>

            <div className="ml-auto flex justify-end gap-4">
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
                onClick={() => setCreateModalOpen(true)}
              >
                <LucidePlus />
                {t('admin.newGroup')}
              </Button>
            </div>
          </CardHeader>

          <CardContent>
            <Table>
              <colgroup>
                <col className="w-[25%]" />
                <col className="w-[40%]" />
                <col className="w-[15%]" />
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
          </CardContent>

          <CardFooter className="flex items-center justify-end">
            <RAGFlowPagination
              total={groupsList?.length ?? 0}
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

      {/* Create Group Modal */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.createGroup')}</DialogTitle>
          </DialogHeader>

          <section className="px-6 space-y-4">
            <div>
              <Label>{t('admin.groupName')}</Label>
              <Input
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder={t('admin.enterGroupName')}
              />
            </div>
            <div>
              <Label>{t('admin.description')}</Label>
              <Textarea
                value={groupDescription}
                onChange={(e) => setGroupDescription(e.target.value)}
                placeholder={t('admin.enterDescription')}
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={isAdmin} onCheckedChange={setIsAdmin} />
              <Label>{t('admin.adminGroup')}</Label>
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
                createGroupMutation.mutate({
                  name: groupName,
                  description: groupDescription,
                  is_admin: isAdmin,
                })
              }
              disabled={!groupName || createGroupMutation.isPending}
              loading={createGroupMutation.isPending}
            >
              {t('admin.create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Group Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.editGroup')}</DialogTitle>
          </DialogHeader>

          <section className="px-6 space-y-4">
            <div>
              <Label>{t('admin.groupName')}</Label>
              <Input
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder={t('admin.enterGroupName')}
              />
            </div>
            <div>
              <Label>{t('admin.description')}</Label>
              <Textarea
                value={groupDescription}
                onChange={(e) => setGroupDescription(e.target.value)}
                placeholder={t('admin.enterDescription')}
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={isAdmin} onCheckedChange={setIsAdmin} />
              <Label>{t('admin.adminGroup')}</Label>
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
                selectedGroup &&
                updateGroupMutation.mutate({
                  id: selectedGroup.id,
                  data: {
                    name: groupName,
                    description: groupDescription,
                    is_admin: isAdmin,
                  },
                })
              }
              disabled={!groupName || updateGroupMutation.isPending}
              loading={updateGroupMutation.isPending}
            >
              {t('admin.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Group Modal */}
      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.deleteGroup')}</DialogTitle>
          </DialogHeader>

          <section className="px-6">
            <DialogDescription>
              {t('admin.deleteGroupConfirmation')}
            </DialogDescription>
            <div className="rounded-lg mt-6 p-4 border-0.5 border-border-button">
              {selectedGroup?.name}
            </div>
          </section>

          <DialogFooter className="gap-4 px-6 py-4">
            <Button variant="outline" onClick={() => setDeleteModalOpen(false)}>
              {t('admin.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() =>
                selectedGroup && deleteGroupMutation.mutate(selectedGroup.id)
              }
              disabled={deleteGroupMutation.isPending}
              loading={deleteGroupMutation.isPending}
            >
              {t('admin.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Group Members Modal */}
      <Dialog open={membersModalOpen} onOpenChange={setMembersModalOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {t('admin.groupMembers')}: {selectedGroup?.name}
            </DialogTitle>
          </DialogHeader>

          <section className="px-6">
            <div className="flex justify-end mb-4">
              <Button onClick={() => setAddMemberModalOpen(true)}>
                <LucideUserPlus className="mr-2" />
                {t('admin.addMember')}
              </Button>
            </div>

            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('admin.email')}</TableHead>
                    <TableHead>{t('admin.nickname')}</TableHead>
                    <TableHead className="w-24">{t('admin.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(groupMembers as GroupMember[])?.length ? (
                    (groupMembers as GroupMember[]).map((member) => (
                      <TableRow key={member.id}>
                        <TableCell>{member.email}</TableCell>
                        <TableCell>{member.nickname || '-'}</TableCell>
                        <TableCell>
                          <Button
                            variant="danger"
                            size="icon"
                            onClick={() =>
                              selectedGroup &&
                              removeMemberMutation.mutate({
                                groupId: selectedGroup.id,
                                userId: member.user_id,
                              })
                            }
                            disabled={removeMemberMutation.isPending}
                          >
                            <LucideTrash2 />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center py-8">
                        {t('admin.noMembers')}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </section>

          <DialogFooter className="px-6 py-4">
            <Button
              variant="outline"
              onClick={() => setMembersModalOpen(false)}
            >
              {t('admin.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Member Modal */}
      <Dialog open={addMemberModalOpen} onOpenChange={setAddMemberModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.addMember')}</DialogTitle>
          </DialogHeader>

          <section className="px-6">
            <div className="border rounded-lg max-h-80 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('admin.email')}</TableHead>
                    <TableHead className="w-24">{t('admin.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {availableUsers?.length ? (
                    availableUsers.map((user: AdminService.ListUsersItem) => (
                      <TableRow key={user.id}>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>
                          <Button
                            size="sm"
                            onClick={() =>
                              selectedGroup &&
                              addMemberMutation.mutate({
                                groupId: selectedGroup.id,
                                userId: user.id,
                              })
                            }
                            disabled={addMemberMutation.isPending}
                          >
                            {t('admin.add')}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={2} className="text-center py-8">
                        {t('admin.noAvailableUsers')}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </section>

          <DialogFooter className="px-6 py-4">
            <Button
              variant="outline"
              onClick={() => setAddMemberModalOpen(false)}
            >
              {t('admin.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default AdminGroups;
