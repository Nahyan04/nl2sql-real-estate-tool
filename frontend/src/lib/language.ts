import type { Lang, LanguageChoice } from "./types";

export function resolveLanguage(question: string, choice: LanguageChoice): Lang {
  if (choice !== "auto") return choice;
  return /[\u0600-\u06FF]/.test(question) ? "ar" : "en";
}
