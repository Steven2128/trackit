/** Native: no document picker installed — statements are uploaded from
 * the web app. Returns null so the caller can tell the user. */
export async function pickPdf(): Promise<File | null> {
  return null;
}

export const canPickPdf = false;
