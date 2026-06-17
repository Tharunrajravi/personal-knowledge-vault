// components/PKVLogo.jsx — Brand logo component
// Usage: <PKVLogo size="md" variant="icon" />

export default function PKVLogo({ size = "md", variant = "full", className = "" }) {
  const sizes = {
    xs: { icon: 24, text: 12 },
    sm: { icon: 32, text: 14 },
    md: { icon: 40, text: 18 },
    lg: { icon: 56, text: 24 },
    xl: { icon: 80, text: 32 },
  }
  const s = sizes[size] || sizes.md

  const Icon = ({ w, h }) => (
    <svg width={w} height={h} viewBox="0 0 140 140" fill="none">
      <defs>
        <linearGradient id="pkv-brain" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2dd4bf"/>
          <stop offset="100%" stopColor="#a78bfa"/>
        </linearGradient>
        <linearGradient id="pkv-key" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#fbbf24"/>
          <stop offset="100%" stopColor="#f59e0b"/>
        </linearGradient>
        <filter id="pkv-glow">
          <feGaussianBlur stdDeviation="1.5" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      {/* Brain outline */}
      <path
        d="M54 58 C54 46 60 40 68 40 C68 36 72 34 76 36 C80 32 87 36 87 42
           C94 42 99 48 99 56 C104 60 104 70 99 74 C101 80 99 88 93 91
           C92 98 85 101 79 99 C76 104 69 104 66 100 C59 102 53 97 53 91
           C46 88 44 79 47 73 C43 68 43 59 54 58Z"
        stroke="url(#pkv-brain)" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round"
        filter="url(#pkv-glow)"
      />
      {/* Brain center */}
      <path d="M76 36 C74 52 74 76 76 100"
        stroke="url(#pkv-brain)" strokeWidth="1.5"
        strokeDasharray="3 3" opacity="0.7"
      />
      {/* Brain folds left */}
      <path d="M47 73 C54 70 57 64 55 58" stroke="url(#pkv-brain)" strokeWidth="1.8" strokeLinecap="round" opacity="0.8"/>
      <path d="M53 91 C60 88 62 82 59 76" stroke="url(#pkv-brain)" strokeWidth="1.8" strokeLinecap="round" opacity="0.8"/>
      {/* Brain folds right */}
      <path d="M99 74 C93 71 91 65 93 59" stroke="url(#pkv-brain)" strokeWidth="1.8" strokeLinecap="round" opacity="0.8"/>
      <path d="M93 91 C87 88 86 81 89 75" stroke="url(#pkv-brain)" strokeWidth="1.8" strokeLinecap="round" opacity="0.8"/>

      {/* Key head */}
      <circle cx="76" cy="112" r="8" stroke="url(#pkv-key)" strokeWidth="2.5" filter="url(#pkv-glow)"/>
      <circle cx="76" cy="112" r="3.5" stroke="url(#pkv-key)" strokeWidth="1.5"/>
      {/* Key shaft */}
      <line x1="76" y1="104" x2="76" y2="95" stroke="url(#pkv-key)" strokeWidth="2.5" strokeLinecap="round"/>
      {/* Key teeth */}
      <line x1="76" y1="98" x2="81" y2="98" stroke="url(#pkv-key)" strokeWidth="2" strokeLinecap="round"/>
      <line x1="76" y1="95" x2="80" y2="95" stroke="url(#pkv-key)" strokeWidth="2" strokeLinecap="round"/>

      {/* Corner dots */}
      <circle cx="30" cy="30" r="2" fill="#2dd4bf" opacity="0.4"/>
      <circle cx="110" cy="30" r="2" fill="#a78bfa" opacity="0.4"/>
      <circle cx="30" cy="110" r="2" fill="#a78bfa" opacity="0.4"/>
      <circle cx="110" cy="110" r="2" fill="#2dd4bf" opacity="0.4"/>
    </svg>
  )

  if (variant === "icon") {
    return (
      <div className={`relative flex-shrink-0 ${className}`}
           style={{ width: s.icon, height: s.icon }}>
        <div style={{
          position: 'absolute', inset: 0,
          borderRadius: Math.round(s.icon * 0.23),
          background: 'linear-gradient(135deg, #0d9488 0%, #0891b2 50%, #6366f1 100%)',
          boxShadow: `0 0 ${s.icon * 0.4}px rgba(13,148,136,0.4)`
        }}>
          <div style={{
            position: 'absolute', inset: 1,
            borderRadius: Math.round(s.icon * 0.21),
            background: 'linear-gradient(135deg, #0a1628 0%, #0d1f3c 100%)'
          }}/>
        </div>
        <div style={{ position: 'absolute', inset: 0 }}>
          <Icon w={s.icon} h={s.icon} />
        </div>
      </div>
    )
  }

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <div className="relative flex-shrink-0"
           style={{ width: s.icon, height: s.icon }}>
        <div style={{
          position: 'absolute', inset: 0,
          borderRadius: Math.round(s.icon * 0.23),
          background: 'linear-gradient(135deg, #0d9488 0%, #0891b2 50%, #6366f1 100%)',
          boxShadow: `0 0 ${s.icon * 0.4}px rgba(13,148,136,0.35)`
        }}>
          <div style={{
            position: 'absolute', inset: 1,
            borderRadius: Math.round(s.icon * 0.21),
            background: 'linear-gradient(135deg, #0a1628 0%, #0d1f3c 100%)'
          }}/>
        </div>
        <div style={{ position: 'absolute', inset: 0 }}>
          <Icon w={s.icon} h={s.icon} />
        </div>
      </div>
      <div className="flex flex-col leading-tight">
        <span style={{
          fontSize: s.text,
          fontWeight: 700,
          letterSpacing: '-0.5px',
          background: 'linear-gradient(135deg, #2dd4bf, #818cf8)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        }}>
          Knowledge
        </span>
        <span style={{
          fontSize: s.text * 0.85,
          fontWeight: 600,
          letterSpacing: '-0.3px',
          background: 'linear-gradient(135deg, #818cf8, #a78bfa)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        }}>
          Vault
        </span>
      </div>
    </div>
  )
}
