/** Web: a hidden file input. Resolves null if the user cancels. */
export function pickPdf(): Promise<File | null> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/pdf,.pdf";
    input.onchange = () => resolve(input.files?.[0] ?? null);
    // Browsers that report cancel fire "cancel"; others just never change.
    input.addEventListener("cancel", () => resolve(null));
    input.click();
  });
}

export const canPickPdf = true;
