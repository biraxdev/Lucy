import { useEffect, useRef } from 'react'
import * as L from 'leaflet'
import { useAgentStore } from '../stores/agentStore'

export default function MapPage() {
  const agents = useAgentStore((s) => s.agentsArray)
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<any>(null)
  const markers = useRef<any[]>([])

  useEffect(() => {
    if (typeof window === 'undefined' || !mapRef.current) return
    if (mapInstance.current) return

    const map = L.map(mapRef.current).setView([20, 0], 2)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
    }).addTo(map)
    mapInstance.current = map
  }, [])

  useEffect(() => {
    if (!mapInstance.current) return

    markers.current.forEach((m) => m.remove())
    markers.current = []

    agents.forEach((agent) => {
      const lat = agent.geo_lat
      const lng = agent.geo_lng
      if (!lat || !lng) return

      const color = agent.status === 'online' ? '#22c55e' : '#ef4444'
      const icon = L.divIcon({
        html: `<div style="background:${color};width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,.5)"></div>`,
        className: '',
        iconSize: [12, 12],
      })
      const marker = L.marker([lat, lng], { icon })
        .addTo(mapInstance.current)
        .bindPopup(`
          <b>${agent.hostname}</b><br/>
          ${agent.ip_public || agent.ip_private}<br/>
          OS: ${agent.os}<br/>
          Status: <span style="color:${color}">${agent.status}</span>
        `)
      markers.current.push(marker)
    })
  }, [agents])

  const geoAgents = agents.filter((a) => a.geo_lat && a.geo_lng)

  return (
    <div className="page-container space-y-4 h-[calc(100vh-3.5rem)] flex flex-col">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Agent Map</h1>
        <span className="badge badge-success">{geoAgents.length} / {agents.length} located</span>
      </div>
      {geoAgents.length === 0 && (
        <div className="alert alert-info text-sm">No agents with geolocation data available yet.</div>
      )}
      <div ref={mapRef} className="flex-1 rounded-xl overflow-hidden border border-base-300" style={{ minHeight: 400 }} />
    </div>
  )
}
