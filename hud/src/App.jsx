import React, { useEffect, useState } from 'react'
import { MetalFx } from 'metal-fx'
import './app.css'

const LABELS = {
  recording: 'Słucham…',
  processing: 'Przetwarzam…',
}

export default function App() {
  const [state, setState] = useState('idle')

  useEffect(() => {
    // wywoływane z Pythona przez window.evaluate_js
    window.setHudState = (next) => setState(next)
    return () => { delete window.setHudState }
  }, [])

  const visible = state === 'recording' || state === 'processing'

  return (
    <div className={`hud-root ${visible ? 'visible' : 'hidden'}`}>
      <MetalFx variant="button" preset="chromatic" theme="dark" paused={!visible}>
        <div className={`hud-pill state-${state}`}>
          <span className="hud-indicator">
            {state === 'recording' && <span className="dot-pulse" />}
            {state === 'processing' && <span className="spinner" />}
          </span>
          <span className="hud-label">{LABELS[state] ?? ''}</span>
        </div>
      </MetalFx>
    </div>
  )
}
