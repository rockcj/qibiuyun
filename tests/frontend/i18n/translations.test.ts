/** 国际化翻译完整性测试 – 中英文 key 对齐 */

import { translations, type TranslationKey } from "@/i18n/translations";

describe("translations", () => {
  const zhKeys = Object.keys(translations.zh);
  const enKeys = Object.keys(translations.en);

  it("中英文翻译 key 应完全对齐", () => {
    expect(zhKeys.sort()).toEqual(enKeys.sort());
  });

  it("Step 2 新增 key 应存在", () => {
    const requiredKeys: TranslationKey[] = [
      "resume.title",
      "jd.title",
      "setup.title",
      "config.nextSetup",
      "session.created",
    ];
    for (const key of requiredKeys) {
      expect(translations.zh[key]).toBeTruthy();
      expect(translations.en[key]).toBeTruthy();
    }
  });

  it("所有翻译值不应为空字符串", () => {
    for (const key of zhKeys) {
      expect(translations.zh[key as TranslationKey].length).toBeGreaterThan(0);
      expect(translations.en[key as TranslationKey].length).toBeGreaterThan(0);
    }
  });
});
