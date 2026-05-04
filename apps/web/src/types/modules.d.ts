// Type declarations for modules without type definitions
declare module "react-i18next" {
  export function useTranslation(): {
    t: (key: string) => string;
    i18n: { language: string; changeLanguage: (lang: string) => Promise<void> };
  };
  export function initReactI18next(): void;
}

declare module "i18next" {
  const i18next: {
    use: (plugin: unknown) => typeof i18next;
    init: (options: Record<string, unknown>) => Promise<void>;
    language: string;
    changeLanguage: (lang: string) => Promise<void>;
  };
  export default i18next;
}

declare module "i18next-browser-languagedetector" {
  const detector: unknown;
  export default detector;
}

declare module "smiles-drawer" {
  export default class SmilesDrawer {
    static apply(options?: Record<string, unknown>): SmilesDrawer;
    draw(parsed: unknown, canvas: HTMLCanvasElement, theme?: string): void;
  }
  export class SvgDrawer {
    draw(parsed: unknown, svg: SVGElement, theme?: string): void;
  }
  export function parse(smiles: string, callback: (tree: unknown) => void, errback?: (err: unknown) => void): void;
}
