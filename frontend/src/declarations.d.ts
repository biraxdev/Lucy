declare module 'react-syntax-highlighter' {
  import * as React from 'react'
  export interface SyntaxHighlighterProps {
    language?: string
    style?: any
    children?: React.ReactNode
    className?: string
    PreTag?: string | React.ComponentType<any>
    [key: string]: any
  }
  export const Prism: React.FC<SyntaxHighlighterProps>
  export const Light: React.FC<SyntaxHighlighterProps>
}

declare module 'react-syntax-highlighter/dist/esm/styles/prism' {
  export const vscDarkPlus: any
  export const atomDark: any
  export const oneDark: any
  export const prism: any
  export const okaidia: any
}
