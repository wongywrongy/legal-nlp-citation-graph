import { LeftRail } from './LeftRail';
import { TopBar } from './TopBar';
import { InspectorPanel } from './InspectorPanel';
import { CommandPalette } from '@/components/primitives/CommandPalette';
import { KeyboardShortcuts } from '@/components/primitives/KeyboardShortcuts';
import { UploadModal } from '@/components/upload/UploadModal';
import { GlobalDropOverlay } from '@/components/upload/GlobalDropOverlay';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      <LeftRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex min-h-0 flex-1 overflow-hidden">
          <div className="flex-1 overflow-auto">{children}</div>
          <InspectorPanel />
        </main>
      </div>
      <CommandPalette />
      <KeyboardShortcuts />
      <UploadModal />
      <GlobalDropOverlay />
    </div>
  );
}
