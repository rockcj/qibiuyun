export type Locale = "zh" | "en";

export type TranslationKey = keyof (typeof translations)["zh"];

export const translations = {
  zh: {
    "header.subtitle": "AI 实时场景英语口语陪练",
    "hero.title1": "在真实场景中对话。",
    "hero.title2": "在犯错中学习。",
    "hero.title3": "说得更好。",
    "hero.subtitle":
      "选择真实场景，与 AI 角色对话：模拟面试官、餐厅服务员、会议同事……实时纠正发音/语法，生成可量化的口语成长报告。",
    "scene.startTraining": "开始训练",
    "scene.backHome": "返回首页",
    "scene.topics": "对话主题",
    "scene.roles": "AI 角色",
    "scene.rubric": "评分维度",
    "scene.requiresResume": "* 面试场景需要上传简历或输入 JD",
    "footer.text": "OfferGPT · 七牛云 × XEngineer 暑期实训营 · AI 英语口语陪练",
    "lang.switch": "English",
  },
  en: {
    "header.subtitle": "AI Real-Scene English Speaking Coach",
    "hero.title1": "Talk in real scenes.",
    "hero.title2": "Learn from mistakes.",
    "hero.title3": "Speak better.",
    "hero.subtitle":
      "Choose a real-world scenario and talk with an AI character — interviewer, waiter, meeting colleague… Get real-time pronunciation & grammar corrections and a quantifiable speaking growth report.",
    "scene.startTraining": "Start Training",
    "scene.backHome": "Back to Home",
    "scene.topics": "Topics",
    "scene.roles": "AI Roles",
    "scene.rubric": "Scoring Rubric",
    "scene.requiresResume": "* Resume or JD upload required for interview",
    "footer.text": "OfferGPT · Qiniu Cloud × XEngineer Summer Camp · AI English Speaking Coach",
    "lang.switch": "中文",
  },
} as const;
