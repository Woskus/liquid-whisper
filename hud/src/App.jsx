import React, { useEffect, useRef, useState } from 'react'
import { MetalFx } from 'metal-fx'
import './app.css'

// mnożniki słupków — środek reaguje najmocniej, brzegi łagodniej
const BAR_SHAPE = [0.55, 0.85, 1.0, 0.85, 0.55]
const BAR_MIN = 3
const BAR_MAX = 18

export default function App() {
  const [state, setState] = useState('idle')
  const [level, setLevel] = useState(0)
  const smooth = useRef(0)

  useEffect(() => {
    // wywoływane z Pythona przez window.evaluate_js
    window.setHudState = (next) => setState(next)
    window.setHudLevel = (l) => {
      smooth.current = smooth.current * 0.5 + l * 0.5
      setLevel(smooth.current)
    }
    return () => { delete window.setHudState; delete window.setHudLevel }
  }, [])

  const visible = state === 'recording' || state === 'processing'

  return (
    <div className={`hud-root ${visible ? 'visible' : 'hidden'}`}>
      {/* jeden stały MetalFx — remount drugiej instancji zostawał w opacity:0
          (race na współdzielonym kontekście WebGL); zmienia się tylko dziecko */}
      <MetalFx variant="button" preset="chromatic" theme="dark" paused={!visible}>
        <div className={state === 'processing' ? 'hud-circle' : 'hud-capsule'}>
          {state === 'processing' ? (
            <span className="spinner" />
          ) : (
            BAR_SHAPE.map((mul, i) => (
              <span
                key={i}
                className="bar"
                style={{ height: `${BAR_MIN + (BAR_MAX - BAR_MIN) * Math.min(1, level * mul + 0.06)}px` }}
              />
            ))
          )}
        </div>
      </MetalFx>
    </div>
  )
}
