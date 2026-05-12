# ============================================================
# Add-DeleteProject.ps1
# Run from your MetroStack root folder.
# ============================================================

$ProjectRoot = $PSScriptRoot
$SidebarPath = Join-Path $ProjectRoot "frontend\src\components\ProjectSidebar.tsx"

if (-not (Test-Path $SidebarPath)) {
    Write-Error "Cannot find ProjectSidebar.tsx at: $SidebarPath"
    exit 1
}

# Backup
Copy-Item $SidebarPath "$SidebarPath.bak" -Force
Write-Host "Backup saved: $SidebarPath.bak" -ForegroundColor DarkGray

$c = Get-Content $SidebarPath -Raw

# Patch 1: inject delete mutation into ProjectItem function
$old1 = 'function ProjectItem({ project, isActive, onClick, onClose }: ProjectItemProps) {
  const statusColors = {'

$new1 = 'function ProjectItem({ project, isActive, onClick, onClose }: ProjectItemProps) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => projectsAPI.delete(project.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [''projects''] })
      onClose()
    },
    onError: () => {
      setConfirmDelete(false)
      alert(`Failed to delete "${project.name}". Please try again.`)
    },
  })

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirmDelete) {
      setConfirmDelete(true)
      setTimeout(() => setConfirmDelete(false), 3000)
    } else {
      deleteMutation.mutate()
    }
  }

  const statusColors = {'

if ($c.Contains($old1)) {
    $c = $c.Replace($old1, $new1)
    Write-Host "[1/2] Injected delete mutation into ProjectItem" -ForegroundColor Cyan
} else {
    Write-Host "[1/2] WARNING: Could not find ProjectItem body - check file manually" -ForegroundColor Yellow
}

# Patch 2: replace the X button JSX
$old2 = '              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onClose()
                }}
                className="p-1 rounded hover:bg-industrial-700 text-industrial-400 hover:text-neon-red transition-colors"
                title="Close Project"
              >
                <X size={16} />
              </button>'

$new2 = '              <button
                onClick={handleDeleteClick}
                disabled={deleteMutation.isPending}
                className={clsx(
                  ''p-1 rounded transition-colors text-xs font-mono'',
                  confirmDelete
                    ? ''bg-neon-red/20 text-neon-red border border-neon-red/50 px-2''
                    : ''hover:bg-industrial-700 text-industrial-400 hover:text-neon-red''
                )}
                title={confirmDelete ? ''Click again to confirm delete'' : ''Delete project''}
              >
                {deleteMutation.isPending
                  ? <Loader2 size={14} className="animate-spin" />
                  : confirmDelete
                    ? ''DEL?''
                    : <X size={16} />
                }
              </button>'

if ($c.Contains($old2)) {
    $c = $c.Replace($old2, $new2)
    Write-Host "[2/2] Replaced X button with two-click confirm delete" -ForegroundColor Cyan
} else {
    Write-Host "[2/2] WARNING: Could not find X button block - check file manually" -ForegroundColor Yellow
}

Set-Content $SidebarPath $c -Encoding UTF8 -NoNewline
Write-Host ""
Write-Host "Done. ProjectSidebar.tsx updated." -ForegroundColor Green
Write-Host "First X click  -> turns red, shows DEL? for 3s"
Write-Host "Second X click -> fires DELETE /projects/{id}"
Write-Host "To undo: rename ProjectSidebar.tsx.bak back to ProjectSidebar.tsx"
