import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import { useCopilotStore } from '../stores/copilotStore'

export function CopilotFab() {
  const { open, toggleOpen } = useCopilotStore()

  // Global keybind: Ctrl+J
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
        e.preventDefault()
        toggleOpen()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [toggleOpen])

  return (
    <AnimatePresence>
      {!open && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.8, y: 20 }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          onClick={toggleOpen}
          className="fixed bottom-6 right-6 z-[150] flex items-center gap-2 px-4 py-3 rounded-2xl
                     bg-success text-success-content shadow-[0_0_24px_rgba(0,255,157,0.3)]
                     hover:shadow-[0_0_36px_rgba(0,255,157,0.5)] transition-shadow
                     border border-success/30 group"
          title="Ouvrir le Copilot (Ctrl+J)"
        >
          <div className="relative">
            <Sparkles size={20} className="animate-pulse" />
            <div className="absolute inset-0 rounded-full bg-success/20 animate-ping" />
          </div>
          <span className="text-sm font-semibold hidden sm:inline">Lucy Copilot</span>
          <kbd className="kbd kbd-xs hidden sm:inline-block opacity-70">Ctrl+J</kbd>
        </motion.button>
      )}
    </AnimatePresence>
  )
}
