/** @type {import('tailwindcss').Config} */
const colors = require("tailwindcss/colors");

module.exports = {
    darkMode: ["class"],
    content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: {
  	extend: {
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		colors: {
  			// These are full colours supplied by the federation token bridge
  			// (shadcn-bridge.css), consumed as-is. Only the Hub's own --status-*
  			// values below are still HSL channels and still wrapped in hsl().
  			background: 'var(--background)',
  			foreground: 'var(--foreground)',
  			card: {
  				DEFAULT: 'var(--card)',
  				foreground: 'var(--card-foreground)'
  			},
  			popover: {
  				DEFAULT: 'var(--popover)',
  				foreground: 'var(--popover-foreground)'
  			},
  			primary: {
  				DEFAULT: 'var(--primary)',
  				foreground: 'var(--primary-foreground)'
  			},
  			secondary: {
  				DEFAULT: 'var(--secondary)',
  				foreground: 'var(--secondary-foreground)'
  			},
  			muted: {
  				DEFAULT: 'var(--muted)',
  				foreground: 'var(--muted-foreground)'
  			},
  			accent: {
  				DEFAULT: 'var(--accent)',
  				foreground: 'var(--accent-foreground)'
  			},
  			destructive: {
  				DEFAULT: 'var(--destructive)',
  				foreground: 'var(--destructive-foreground)'
  			},
  			border: 'var(--border)',
  			input: 'var(--input)',
  			ring: 'var(--ring)',
  			chart: {
  				'1': 'var(--chart-1)',
  				'2': 'var(--chart-2)',
  				'3': 'var(--chart-3)',
  				'4': 'var(--chart-4)',
  				'5': 'var(--chart-5)'
  			},
  			sidebar: {
  				DEFAULT: 'var(--sidebar-background)',
  				foreground: 'var(--sidebar-foreground)',
  				primary: 'var(--sidebar-primary)',
  				'primary-foreground': 'var(--sidebar-primary-foreground)',
  				accent: 'var(--sidebar-accent)',
  				'accent-foreground': 'var(--sidebar-accent-foreground)',
  				border: 'var(--sidebar-border)',
  				ring: 'var(--sidebar-ring)'
  			},
  			status: {
  				danger: { DEFAULT: 'hsl(var(--status-danger))', fg: 'hsl(var(--status-danger-fg))' },
  				success: { DEFAULT: 'hsl(var(--status-success))', fg: 'hsl(var(--status-success-fg))' },
  				warning: { DEFAULT: 'hsl(var(--status-warning))', fg: 'hsl(var(--status-warning-fg))' },
  				info: { DEFAULT: 'hsl(var(--status-info))', fg: 'hsl(var(--status-info-fg))' },
  				neutral: { DEFAULT: 'hsl(var(--status-neutral))', fg: 'hsl(var(--status-neutral-fg))' },
  				process: { DEFAULT: 'hsl(var(--status-process))', fg: 'hsl(var(--status-process-fg))' },
  				tier: { DEFAULT: 'hsl(var(--status-tier))', fg: 'hsl(var(--status-tier-fg))' },
  				caution: { DEFAULT: 'hsl(var(--status-caution))', fg: 'hsl(var(--status-caution-fg))' },
  				elevated: { DEFAULT: 'hsl(var(--status-elevated))', fg: 'hsl(var(--status-elevated-fg))' }
  			},
  			fed: {
  				controlplane: { DEFAULT: colors.slate[500], dot: colors.slate[300], fg: colors.slate[300] },
  				networkgraph: { DEFAULT: colors.violet[500], dot: colors.violet[400], fg: colors.violet[300] },
  				uap: { DEFAULT: colors.lime[500], dot: colors.lime[400], fg: colors.lime[300] },
  				infrastructure: { DEFAULT: colors.teal[500], dot: colors.teal[400], fg: colors.teal[300] },
  				contracts: { DEFAULT: colors.emerald[500], dot: colors.emerald[400], fg: colors.emerald[300] },
  				airspace: { DEFAULT: colors.sky[500], dot: colors.sky[400], fg: colors.sky[300] },
  				signals: { DEFAULT: colors.orange[500], dot: colors.orange[400], fg: colors.orange[300] }
  			}
  		},
  		fontFamily: {
  			heading: ['var(--font-heading)'],
  			body: ['var(--font-body)'],
  			display: ['var(--font-display)'],
  			mono: ['var(--font-mono)']
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
}
