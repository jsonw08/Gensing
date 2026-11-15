import { type KeyboardEvent, useEffect, useRef, useState } from 'react'
import { Icon } from './Icon'

export type MenuItem = { label: string; onSelect?: () => void; disabled?: boolean; checked?: boolean } | 'separator'
export type Menu = { label: string; items: MenuItem[] }

// The desktop's menu bar. Click a title to open its menu; while one is open, pointing at another
// title switches to it. Keyboard: arrows move between items and menus, Enter picks, Escape closes.
export function MenuBar({ menus }: { menus: Menu[] }) {
  const [open, setOpen] = useState<number | null>(null)
  const barRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open === null) return
    const close = (e: PointerEvent) => {
      if (!barRef.current?.contains(e.target as Node)) setOpen(null)
    }
    window.addEventListener('pointerdown', close)
    return () => window.removeEventListener('pointerdown', close)
  }, [open])

  const items = (i: number) => [...(barRef.current?.querySelectorAll<HTMLButtonElement>(`[data-menu="${i}"] .menu-item:not(:disabled)`) ?? [])]
  const titles = () => [...(barRef.current?.querySelectorAll<HTMLButtonElement>('.menu-title') ?? [])]

  const openMenu = (i: number, focusFirst = false) => {
    setOpen(i)
    if (focusFirst) requestAnimationFrame(() => items(i)[0]?.focus())
  }

  const onTitleKey = (e: KeyboardEvent, i: number) => {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openMenu(i, true)
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault()
      const next = (i + (e.key === 'ArrowRight' ? 1 : menus.length - 1)) % menus.length
      titles()[next]?.focus()
      if (open !== null) openMenu(next)
    }
  }

  const onMenuKey = (e: KeyboardEvent, i: number) => {
    const list = items(i)
    const at = list.indexOf(document.activeElement as HTMLButtonElement)
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const step = e.key === 'ArrowDown' ? 1 : list.length - 1
      list[(at + step) % list.length]?.focus()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setOpen(null)
      titles()[i]?.focus()
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault()
      const next = (i + (e.key === 'ArrowRight' ? 1 : menus.length - 1)) % menus.length
      openMenu(next, true)
    }
  }

  return (
    <div className="menubar" role="menubar" ref={barRef}>
      <span className="menubar-brand">
        <Icon name="note" />
        Gensing
      </span>
      {menus.map((menu, i) => (
        <div key={menu.label} className="menu" data-menu={i}>
          <button
            type="button"
            className={`menu-title${open === i ? ' open' : ''}`}
            role="menuitem"
            aria-haspopup="menu"
            aria-expanded={open === i}
            onClick={() => setOpen(open === i ? null : i)}
            onPointerEnter={() => open !== null && open !== i && setOpen(i)}
            onKeyDown={(e) => onTitleKey(e, i)}
          >
            {menu.label}
          </button>
          {open === i && (
            <div className="menu-list" role="menu" aria-label={menu.label} onKeyDown={(e) => onMenuKey(e, i)}>
              {menu.items.map((item, j) =>
                item === 'separator' ? (
                  <div key={j} className="menu-sep" role="separator" />
                ) : (
                  <button
                    key={j}
                    type="button"
                    role="menuitem"
                    className="menu-item"
                    disabled={item.disabled}
                    onClick={() => {
                      setOpen(null)
                      item.onSelect?.()
                    }}
                  >
                    <span className="menu-check">{item.checked && <Icon name="check" />}</span>
                    {item.label}
                  </button>
                ),
              )}
            </div>
          )}
        </div>
      ))}
      <Clock />
    </div>
  )
}

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15_000)
    return () => clearInterval(id)
  }, [])
  return <span className="menubar-clock">{now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
}
