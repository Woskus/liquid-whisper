import React, { useEffect, useRef, useState } from 'react'
import { MetalFx } from 'metal-fx'
import './app.css'

// mnożniki słupków — środek reaguje najmocniej, brzegi łagodniej
const BAR_SHAPE = [0.55, 0.85, 1.0, 0.85, 0.55]
const BAR_MIN = 3
const BAR_MAX = 18

const TEXT_TAIL = 70 // pokazujemy końcówkę — najświeższe słowa

export default function App() {
  const [state, setState] = useState('idle')
  const [level, setLevel] = useState(0)
  const [text, setText] = useState('')
  const smooth = useRef(0)

  useEffect(() => {
    // wywoływane z Pythona przez window.evaluate_js
    window.setHudState = (next) => setState(next)
    window.setHudLevel = (l) => {
      smooth.current = smooth.current * 0.5 + l * 0.5
      setLevel(smooth.current)
    }
    window.setHudText = (t) => setText(t)
    return () => { delete window.setHudState; delete window.setHudLevel; delete window.setHudText }
  }, [])

  useEffect(() => {
    if (state === 'idle') setText('')
  }, [state])

  const visible = state === 'recording' || state === 'processing'
  const tail = text.length > TEXT_TAIL ? '…' + text.slice(-TEXT_TAIL) : text

  return (
    <div className={`hud-root ${visible ? 'visible' : 'hidden'}`}>
      {/* jeden stały MetalFx — remount drugiej instancji zostawał w opacity:0
          (race na współdzielonym kontekście WebGL); zmienia się tylko dziecko.
          Przetwarzanie: te same słupki, ale w automatycznej fali — spójny język
          wizualny zamiast osobnego spinnera */}
      <MetalFx variant="button" preset="chromatic" theme="dark" paused={!visible}>
        <div className="hud-capsule">
          {BAR_SHAPE.map((mul, i) => (
            <span
              key={i}
              className={`bar ${state === 'processing' ? 'wave' : ''}`}
              style={
                state === 'processing'
                  ? { animationDelay: `${i * 0.13}s` }
                  : { height: `${BAR_MIN + (BAR_MAX - BAR_MIN) * Math.min(1, level * mul + 0.06)}px` }
              }
            />
          ))}
        </div>
      </MetalFx>
      {visible && tail && <div className="hud-text">{tail}</div>}
    </div>
  )
}
