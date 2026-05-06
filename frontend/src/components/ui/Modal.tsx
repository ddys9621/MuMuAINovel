import { useEffect, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full'

const SIZE_MAP: Record<ModalSize, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-2xl',
  '2xl': 'max-w-4xl',
  full: 'max-w-[min(1200px,calc(100vw-32px))]',
}

interface ModalProps {
  open?: boolean
  title?: ReactNode
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  size?: ModalSize
  closable?: boolean
  bodyClassName?: string
  closeOnMaskClick?: boolean
  hideHeader?: boolean
}

export function Modal({
  open = true,
  title,
  onClose,
  children,
  footer,
  size = 'xl',
  closable = true,
  bodyClassName,
  closeOnMaskClick = true,
  hideHeader = false,
}: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && closable) onClose()
    }
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onClose, closable])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm px-4 py-8 sm:py-12 animate-fade-in"
      onClick={() => closeOnMaskClick && closable && onClose()}
    >
      <div
        className={cn(
          'relative flex w-full flex-col bg-white shadow-xl border border-surface-border animate-scale-in',
          'max-h-[calc(100dvh-6rem)]',
          SIZE_MAP[size],
        )}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {!hideHeader && (
          <div className="relative flex items-start justify-between gap-4 border-b border-surface-border bg-gradient-to-r from-surface/40 via-white to-white px-6 py-4 flex-shrink-0">
            <span className="absolute left-0 top-3 bottom-3 w-1 bg-brand" aria-hidden />
            <h2 className="text-base font-semibold text-content leading-6 pl-2">{title}</h2>
            {closable && (
              <button
                type="button"
                onClick={onClose}
                className="text-content-tertiary hover:text-content hover:bg-surface-hover -mt-1 -mr-1 p-1.5 transition-colors"
                aria-label="关闭"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        )}
        <div className={cn('flex-1 overflow-y-auto px-6 py-5', bodyClassName)}>
          {children}
        </div>
        {footer && (
          <div className="flex items-center justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 flex-shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

export default Modal
