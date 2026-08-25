import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Users, Circle } from 'lucide-react'
import api from '../api/client'
import { useState } from 'react'

interface Operator {
  user_id: string
  username: string
  role: string
  connected_at: string
  last_activity: string
  current_page: string
}

const roleColors: Record<string, string> = {
  superadmin: 'text-rose-400',
  admin: 'text-amber-400',
  operator: 'text-emerald-400',
  viewer: 'text-sky-400',
}

export function OperatorPresence() {
  const [showList, setShowList] = useState(false)
  const { data: operators = [] } = useQuery({
    queryKey: ['operators-online'],
    queryFn: () => api.get<Operator[]>('/operators/online').then(r => r.data),
    refetchInterval: 10_000,
  })

  return (
    <div className="relative">
      <button
        onClick={() => setShowList(s => !s)}
        className="flex items-center gap-1.5 px-2 py-1 rounded-lg hover:bg-base-300 transition-colors"
        title={`${operators.length} operator(s) online`}
      >
        <Users size={14} className="text-base-content/60" />
        <span className="text-xs font-medium">{operators.length}</span>
        {operators.length > 0 && (
          <Circle size={6} className="fill-emerald-400 text-emerald-400 animate-pulse" />
        )}
      </button>

      <AnimatePresence>
        {showList && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="absolute right-0 top-full mt-2 w-64 bg-base-100 border border-base-300 rounded-xl shadow-xl z-50 overflow-hidden"
          >
            <div className="px-3 py-2 border-b border-base-300 bg-base-200/50">
              <p className="text-[10px] font-bold uppercase tracking-wider text-base-content/40">
                Operators Online ({operators.length})
              </p>
            </div>
            <div className="max-h-64 overflow-y-auto scrollbar-thin">
              {operators.length === 0 && (
                <p className="text-center text-base-content/30 py-6 text-xs">No other operators online.</p>
              )}
              {operators.map((op) => (
                <div key={op.user_id} className="flex items-center gap-2 px-3 py-2 hover:bg-base-200 transition-colors">
                  <div className="relative">
                    <div className="w-7 h-7 rounded-full bg-success/20 flex items-center justify-center text-[10px] font-bold text-success">
                      {op.username?.slice(0, 2).toUpperCase() || '??'}
                    </div>
                    <Circle size={6} className="absolute -bottom-0.5 -right-0.5 fill-emerald-400 text-emerald-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-xs font-medium truncate ${roleColors[op.role] || 'text-base-content/70'}`}>
                      {op.username || op.user_id.slice(0, 8)}
                    </p>
                    <p className="text-[9px] text-base-content/40 truncate">
                      {op.role} {op.current_page && `· ${op.current_page}`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
