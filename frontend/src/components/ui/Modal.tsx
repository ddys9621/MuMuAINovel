import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
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

  // 挂到 body：避免被页面布局里的 stacking context（如 relative + z-index / backdrop-filter）困住，
  // 否则 fixed 遮罩会盖不住侧栏和顶栏
  return createPortal(
    <div
      className="hh-modal-mask z-[60]"
      onClick={() => closeOnMaskClick && closable && onClose()}
    >
      <div
        className={cn('hh-modal', SIZE_MAP[size])}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {!hideHeader && (
          <div className="hh-modal-head items-center py-4">
            <h2 className="text-base font-semibold leading-6 text-content">{title}</h2>
            {closable && (
              <button
                type="button"
                onClick={onClose}
                className="hh-icon-btn-plain -mr-2"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
        <div className={cn('hh-modal-body', bodyClassName)}>
          {children}
        </div>
        {footer && (
          <div className="hh-modal-foot">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
