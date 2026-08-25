import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Tenant } from '../api/tenants'

interface TenantState {
  activeTenant: Tenant | null
  setActiveTenant: (tenant: Tenant | null) => void
  clearTenant: () => void
}

export const useTenantStore = create<TenantState>()(
  persist(
    (set) => ({
      activeTenant: null,
      setActiveTenant: (tenant) => set({ activeTenant: tenant }),
      clearTenant: () => set({ activeTenant: null }),
    }),
    { name: 'lucy-tenant', partialize: (s) => ({ activeTenant: s.activeTenant }) }
  )
)
