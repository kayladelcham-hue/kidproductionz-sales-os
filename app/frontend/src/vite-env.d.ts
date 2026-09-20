/// <reference types="vite/client" />

declare module '*.css';
declare module '*.png' {
  const url: string;
  export default url;
}

declare module 'react-dom/client' {
  export function createRoot(container: Element | DocumentFragment): {render(node: unknown): void};
}
