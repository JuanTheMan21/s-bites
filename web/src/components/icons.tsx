import type { SVGProps } from 'react'

/** One consistent stroke system (1.75, round caps/joins, `currentColor`) replacing every unicode
 * glyph the app used to stand in for an icon (craft-floor: "unicode glyphs or emoji standing in
 * for an icon system" is a refused default). */
function Icon({ children, ...rest }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4 shrink-0"
      aria-hidden
      {...rest}
    >
      {children}
    </svg>
  )
}

export function IconCheck(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M3 8.5 6.2 11.5 13 4.5" />
    </Icon>
  )
}

export function IconChevronDown(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M4 6 8 10 12 6" />
    </Icon>
  )
}

export function IconChevronRight(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M6 4 10 8 6 12" />
    </Icon>
  )
}

export function IconPlus(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M8 3v10M3 8h10" />
    </Icon>
  )
}

export function IconMinus(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M3 8h10" />
    </Icon>
  )
}

export function IconDot(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props} strokeWidth={0} fill="currentColor">
      <circle cx="8" cy="8" r="3" />
    </Icon>
  )
}

export function IconPlay(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props} strokeWidth={0} fill="currentColor">
      <path d="M4.5 3v10l8-5-8-5Z" />
    </Icon>
  )
}

export function IconPlayhead(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props} strokeWidth={0} fill="currentColor">
      <path d="M8 2v9M4 13h8l-4 3-4-3Z" />
    </Icon>
  )
}

export function IconTrophy(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M5 3h6v4a3 3 0 0 1-3 3 3 3 0 0 1-3-3V3Z" />
      <path d="M5 4H3.5A1.5 1.5 0 0 0 2 5.5 2.5 2.5 0 0 0 4.5 8H5M11 4h1.5A1.5 1.5 0 0 1 14 5.5 2.5 2.5 0 0 1 11.5 8H11" />
      <path d="M8 10v2M6 13.5h4M6.5 13.5V12M9.5 13.5V12" />
    </Icon>
  )
}

export function IconSun(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <circle cx="8" cy="8" r="3" />
      <path d="M8 1.5v1.5M8 13v1.5M2.6 2.6l1 1M12.4 12.4l1 1M1.5 8h1.5M13 8h1.5M2.6 13.4l1-1M12.4 3.6l1-1" />
    </Icon>
  )
}

export function IconMoon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props} strokeWidth={0} fill="currentColor">
      <path d="M13.5 9.8A5.8 5.8 0 0 1 6.2 2.5a5.8 5.8 0 1 0 7.3 7.3Z" />
    </Icon>
  )
}
