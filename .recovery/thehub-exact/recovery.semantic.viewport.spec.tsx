import { readFileSync } from "node:fs";

describe("TheHub recovered viewport semantic supersession",()=>{
  const css=readFileSync("components/HubHeader.module.css","utf8");
  const source=readFileSync("components/HubHeader.tsx","utf8");
  it("contains bounded header layout and responsive mobile navigation without requiring overflow-x:auto",()=>{
    expect(css).toContain("grid-template-columns:minmax(180px,auto) minmax(0,1fr) auto");
    expect(css).toContain(".nav { min-width:0");
    expect(css).toContain("@media(max-width:720px)");
    expect(css).toContain(".nav{display:none}");
    expect(css).toContain(".mobileNav{position:fixed;left:0;right:0;bottom:0");
    expect(css).toContain("env(safe-area-inset-bottom)");
  });
  it("contains semantic labels and keyboard focus/search behavior",()=>{
    expect(source).toContain("aria-label");
    expect(source).toContain("ctrlKey");
    expect(source).toContain("metaKey");
  });
});
