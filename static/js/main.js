// ── i18n translation table ────────────────────────────────────────────────────

const TRANSLATIONS = {

  // ── English ──────────────────────────────────────────────────────────────
  en: {
    "nav.dashboard": "Dashboard",
    "nav.postjob": "Post a Job",
    "nav.browsejobs": "Browse Jobs",
    "nav.profile": "My Profile",
    "nav.logout": "Log Out",
    "nav.login": "Log In",
    "nav.signup": "Sign Up",

    "hero.title1": "Hire the right talent for your",
    "hero.title2": "restaurant",
    "hero.subtitle": "ENTR connects immigrant-owned restaurants with qualified workers, powered by AI.",
    "hero.employer": "I'm Hiring",
    "hero.worker": "I'm Looking for Work",
    "hero.feature1.title": "AI Screening",
    "hero.feature1.desc": "Each application is scored automatically so you see the best matches first.",
    "hero.feature2.title": "Multilingual",
    "hero.feature2.desc": "The platform works in 6 languages — no language barrier.",
    "hero.feature3.title": "Fast & Simple",
    "hero.feature3.desc": "Post a job in under a minute. Apply with just a few taps.",

    "landing.whyTitle": "Built for restaurant owners who work hard",
    "landing.howTitle": "Hire in three simple steps",
    "landing.step1.title": "Post a job",
    "landing.step1.desc": "Describe the role, pay, and hours. Takes about 60 seconds.",
    "landing.step2.title": "Workers apply",
    "landing.step2.desc": "Qualified candidates from your area apply directly.",
    "landing.step3.title": "AI ranks them",
    "landing.step3.desc": "Claude AI scores every application and gives you a clear summary.",
    "landing.cta.title": "Ready to find your next great hire?",
    "landing.cta.sub": "Free to use. No credit card required.",
    "landing.cta.employer": "Post a Job Now",
    "landing.cta.worker": "Find Work",

    "signup.title": "Create your account",
    "signup.subtitle": "Join ENTR — it's free.",
    "signup.name": "Full Name",
    "signup.email": "Email",
    "signup.password": "Password",
    "signup.phone": "Phone (optional)",
    "signup.language": "Preferred Language",
    "signup.role": "I am a...",
    "signup.employer.label": "Restaurant Owner",
    "signup.employer.desc": "I want to hire staff",
    "signup.worker.label": "Job Seeker",
    "signup.worker.desc": "I'm looking for work",
    "signup.restaurant": "Restaurant Name (optional)",
    "signup.submit": "Create Account",
    "signup.login": "Already have an account?",

    "login.title": "Welcome back",
    "login.subtitle": "Sign in to your ENTR account.",
    "login.email": "Email",
    "login.password": "Password",
    "login.submit": "Sign In",
    "login.signup": "Don't have an account?",

    "employer.dashboard.title": "Your Jobs",
    "employer.dashboard.subtitle": "Manage your job listings.",
    "employer.postjob.btn": "Post a Job",
    "employer.job.applications": "View Applications",
    "employer.job.close": "Close Job",
    "employer.job.reopen": "Reopen",
    "employer.job.applicants": "applicants",
    "employer.noJobs": "No jobs posted yet.",
    "employer.noJobs.desc": "Post your first job to start receiving applications.",

    "postjob.title": "Post a Job",
    "postjob.subtitle": "Fill in the details below to find your next team member.",
    "postjob.position": "Position / Title",
    "postjob.pay": "Pay",
    "postjob.pay.hint": "e.g. $18/hr or $600/week",
    "postjob.hours": "Hours",
    "postjob.hours.hint": "e.g. Full-time, Weekends, Mon–Fri 9am–5pm",
    "postjob.experience": "Experience Required (years)",
    "postjob.language": "Language Preference",
    "postjob.language.hint": "e.g. Spanish, English, Bilingual",
    "postjob.location": "Location",
    "postjob.description": "Job Description (optional)",
    "postjob.submit": "Post Job",

    "applications.title": "Applications for",
    "applications.back": "Back to Dashboard",
    "applications.noApps": "No applications yet.",
    "applications.noApps.desc": "Applications will appear here once workers apply.",
    "applications.score": "AI Match Score",
    "applications.summary": "AI Summary",
    "applications.experience": "Experience",
    "applications.languages": "Languages",
    "applications.phone": "Phone",
    "applications.coverletter": "Cover Letter",
    "applications.status": "Status",
    "applications.updateStatus": "Update",

    "worker.dashboard.title": "My Applications",
    "worker.dashboard.subtitle": "Track the status of your job applications.",
    "worker.browseBtn": "Browse Open Jobs",
    "worker.noApps": "No applications yet.",
    "worker.noApps.desc": "Browse open jobs and apply to get started.",

    "browse.title": "Open Jobs",
    "browse.subtitle": "Find your next opportunity.",
    "browse.apply": "Apply Now",
    "browse.applied": "Applied",
    "browse.noJobs": "No open jobs right now.",
    "browse.noJobs.desc": "Check back soon for new opportunities.",
    "browse.pay": "Pay",
    "browse.hours": "Hours",
    "browse.experience": "Experience",
    "browse.language": "Language",

    "apply.title": "Apply for",
    "apply.coverletter": "Cover Letter (optional)",
    "apply.coverletter.hint": "Tell the employer why you'd be a great fit.",
    "apply.submit": "Submit Application",
    "apply.back": "Back to Jobs",

    "profile.title": "My Profile",
    "profile.subtitle": "Keep your profile updated to improve your match score.",
    "profile.bio": "Skills & Experience",
    "profile.bio.hint": "Describe your restaurant experience, skills, and what kind of work you're looking for.",
    "profile.years": "Years of Experience",
    "profile.languages": "Languages Spoken",
    "profile.languages.hint": "e.g. English, Spanish, Mandarin",
    "profile.phone": "Phone",
    "profile.save": "Save Profile",

    "years.abbr": "yrs exp.",
    "status.pending": "Pending",
    "status.reviewed": "Reviewed",
    "status.accepted": "Accepted",
    "status.rejected": "Rejected",
    "status.open": "Open",
    "status.closed": "Closed",
    "status.interview_scheduled": "Interview Scheduled",

    "forgotpassword.title": "Forgot your password?",
    "forgotpassword.subtitle": "Enter your email and we'll send a reset link.",
    "forgotpassword.hint": "We'll email a link to reset your password.",
    "forgotpassword.submit": "Send Reset Link",

    "resetpassword.title": "Reset your password",
    "resetpassword.confirm": "Confirm password",
    "resetpassword.submit": "Reset Password",

    "password.weak": "Weak",
    "password.ok": "OK",
    "password.strong": "Strong",
    "password.hint": "8+ characters. Mix of letters, numbers, special characters for strong.",

    "availability.title": "When are you available?",
    "availability.subtitle": "Let employers know when you can do a quick call.",
    "availability.days": "Select Days",
    "availability.times": "Select Times",
    "availability.monday": "Monday",
    "availability.tuesday": "Tuesday",
    "availability.wednesday": "Wednesday",
    "availability.thursday": "Thursday",
    "availability.friday": "Friday",
    "availability.saturday": "Saturday",
    "availability.sunday": "Sunday",
    "availability.morning": "Morning",
    "availability.afternoon": "Afternoon",
    "availability.evening": "Evening",
    "availability.submit": "Save Availability",
    "availability.note": "You can update this later in your dashboard. Employers will use this to schedule interviews.",

    "interview.schedule": "Schedule Interview",
    "interview.scheduled": "Interview Scheduled",
    "interview.time": "Interview Time",
    "interview.with": "Interview with",
    "interview.confirm": "Confirm Time",
    "interview.add_calendar": "Add to Google Calendar",
    "interview.details": "Interview Details",
    "interview.ready": "You are all set",

    "common.cancel": "Cancel",
  },

  // ── Spanish ───────────────────────────────────────────────────────────────
  es: {
    "nav.dashboard": "Panel",
    "nav.postjob": "Publicar trabajo",
    "nav.browsejobs": "Ver trabajos",
    "nav.profile": "Mi perfil",
    "nav.logout": "Cerrar sesión",
    "nav.login": "Iniciar sesión",
    "nav.signup": "Registrarse",

    "hero.title1": "Contrata al mejor talento para tu",
    "hero.title2": "restaurante",
    "hero.subtitle": "ENTR conecta restaurantes de inmigrantes con trabajadores calificados, impulsado por IA.",
    "hero.employer": "Busco contratar",
    "hero.worker": "Busco trabajo",
    "hero.feature1.title": "Evaluación IA",
    "hero.feature1.desc": "Cada solicitud se puntúa automáticamente para que veas las mejores primero.",
    "hero.feature2.title": "Multilingüe",
    "hero.feature2.desc": "La plataforma funciona en 6 idiomas — sin barreras de idioma.",
    "hero.feature3.title": "Rápido y simple",
    "hero.feature3.desc": "Publica un trabajo en menos de un minuto. Aplica con pocos toques.",

    "landing.whyTitle": "Hecho para dueños de restaurantes que trabajan duro",
    "landing.howTitle": "Contrata en tres pasos simples",
    "landing.step1.title": "Publica un trabajo",
    "landing.step1.desc": "Describe el puesto, salario y horario. Tarda solo 60 segundos.",
    "landing.step2.title": "Los trabajadores aplican",
    "landing.step2.desc": "Candidatos calificados de tu área aplican directamente.",
    "landing.step3.title": "La IA los clasifica",
    "landing.step3.desc": "Claude AI puntúa cada solicitud y te da un resumen claro.",
    "landing.cta.title": "¿Listo para encontrar tu próxima contratación?",
    "landing.cta.sub": "Gratuito. Sin tarjeta de crédito.",
    "landing.cta.employer": "Publicar trabajo",
    "landing.cta.worker": "Buscar trabajo",

    "signup.title": "Crea tu cuenta",
    "signup.subtitle": "Únete a ENTR — es gratis.",
    "signup.name": "Nombre completo",
    "signup.email": "Correo electrónico",
    "signup.password": "Contraseña",
    "signup.phone": "Teléfono (opcional)",
    "signup.language": "Idioma preferido",
    "signup.role": "Soy...",
    "signup.employer.label": "Dueño de restaurante",
    "signup.employer.desc": "Quiero contratar personal",
    "signup.worker.label": "Buscador de trabajo",
    "signup.worker.desc": "Busco empleo",
    "signup.restaurant": "Nombre del restaurante (opcional)",
    "signup.submit": "Crear cuenta",
    "signup.login": "¿Ya tienes cuenta?",

    "login.title": "Bienvenido de nuevo",
    "login.subtitle": "Inicia sesión en tu cuenta de ENTR.",
    "login.email": "Correo electrónico",
    "login.password": "Contraseña",
    "login.submit": "Iniciar sesión",
    "login.signup": "¿No tienes cuenta?",

    "employer.dashboard.title": "Tus trabajos",
    "employer.dashboard.subtitle": "Administra tus ofertas de trabajo.",
    "employer.postjob.btn": "Publicar trabajo",
    "employer.job.applications": "Ver solicitudes",
    "employer.job.close": "Cerrar oferta",
    "employer.job.reopen": "Reabrir",
    "employer.job.applicants": "solicitantes",
    "employer.noJobs": "No hay trabajos publicados.",
    "employer.noJobs.desc": "Publica tu primer trabajo para recibir solicitudes.",

    "postjob.title": "Publicar trabajo",
    "postjob.subtitle": "Completa los detalles para encontrar a tu próximo empleado.",
    "postjob.position": "Puesto / Título",
    "postjob.pay": "Salario",
    "postjob.pay.hint": "p.ej. $18/hr o $600/semana",
    "postjob.hours": "Horario",
    "postjob.hours.hint": "p.ej. Tiempo completo, Fines de semana, Lun–Vie 9am–5pm",
    "postjob.experience": "Experiencia requerida (años)",
    "postjob.language": "Preferencia de idioma",
    "postjob.language.hint": "p.ej. Español, Inglés, Bilingüe",
    "postjob.location": "Ubicación",
    "postjob.description": "Descripción del trabajo (opcional)",
    "postjob.submit": "Publicar",

    "applications.title": "Solicitudes para",
    "applications.back": "Volver al panel",
    "applications.noApps": "Sin solicitudes aún.",
    "applications.noApps.desc": "Las solicitudes aparecerán aquí cuando los trabajadores apliquen.",
    "applications.score": "Puntuación IA",
    "applications.summary": "Resumen IA",
    "applications.experience": "Experiencia",
    "applications.languages": "Idiomas",
    "applications.phone": "Teléfono",
    "applications.coverletter": "Carta de presentación",
    "applications.status": "Estado",
    "applications.updateStatus": "Actualizar",

    "worker.dashboard.title": "Mis solicitudes",
    "worker.dashboard.subtitle": "Sigue el estado de tus solicitudes de empleo.",
    "worker.browseBtn": "Ver trabajos disponibles",
    "worker.noApps": "Sin solicitudes aún.",
    "worker.noApps.desc": "Explora los trabajos disponibles y aplica para comenzar.",

    "browse.title": "Trabajos disponibles",
    "browse.subtitle": "Encuentra tu próxima oportunidad.",
    "browse.apply": "Aplicar ahora",
    "browse.applied": "Ya aplicaste",
    "browse.noJobs": "No hay trabajos abiertos ahora.",
    "browse.noJobs.desc": "Vuelve pronto para nuevas oportunidades.",
    "browse.pay": "Salario",
    "browse.hours": "Horario",
    "browse.experience": "Experiencia",
    "browse.language": "Idioma",

    "apply.title": "Aplicar para",
    "apply.coverletter": "Carta de presentación (opcional)",
    "apply.coverletter.hint": "Cuéntale al empleador por qué serías perfecto.",
    "apply.submit": "Enviar solicitud",
    "apply.back": "Volver a trabajos",

    "profile.title": "Mi perfil",
    "profile.subtitle": "Mantén tu perfil actualizado para mejorar tu puntuación.",
    "profile.bio": "Habilidades y experiencia",
    "profile.bio.hint": "Describe tu experiencia en restaurantes, habilidades y el tipo de trabajo que buscas.",
    "profile.years": "Años de experiencia",
    "profile.languages": "Idiomas hablados",
    "profile.languages.hint": "p.ej. Inglés, Español, Mandarín",
    "profile.phone": "Teléfono",
    "profile.save": "Guardar perfil",

    "years.abbr": "años exp.",
    "status.pending": "Pendiente",
    "status.reviewed": "Revisado",
    "status.accepted": "Aceptado",
    "status.rejected": "Rechazado",
    "status.open": "Abierto",
    "status.closed": "Cerrado",
    "status.interview_scheduled": "Entrevista programada",

    "forgotpassword.title": "¿Olvidaste tu contrasena?",
    "forgotpassword.subtitle": "Ingresa tu correo y te enviaremos un enlace.",
    "forgotpassword.hint": "Te enviaremos un enlace para restablecer tu contrasena.",
    "forgotpassword.submit": "Enviar enlace",

    "resetpassword.title": "Restablecer tu contrasena",
    "resetpassword.confirm": "Confirmar contrasena",
    "resetpassword.submit": "Restablecer contrasena",

    "password.weak": "Debil",
    "password.ok": "OK",
    "password.strong": "Fuerte",
    "password.hint": "8+ caracteres. Mezcla de letras, numeros, caracteres especiales para fuerte.",

    "availability.title": "¿Cuándo estás disponible?",
    "availability.subtitle": "Deja que los empleadores sepan cuándo puedes hacer una llamada.",
    "availability.days": "Selecciona días",
    "availability.times": "Selecciona horarios",
    "availability.monday": "Lunes",
    "availability.tuesday": "Martes",
    "availability.wednesday": "Miércoles",
    "availability.thursday": "Jueves",
    "availability.friday": "Viernes",
    "availability.saturday": "Sábado",
    "availability.sunday": "Domingo",
    "availability.morning": "Mañana",
    "availability.afternoon": "Tarde",
    "availability.evening": "Noche",
    "availability.submit": "Guardar disponibilidad",
    "availability.note": "Puedes actualizar esto después en tu panel. Los empleadores usarán esto para programar entrevistas.",

    "interview.schedule": "Programar entrevista",
    "interview.scheduled": "Entrevista programada",
    "interview.time": "Hora de la entrevista",
    "interview.with": "Entrevista con",
    "interview.confirm": "Confirmar hora",
    "interview.add_calendar": "Agregar a Google Calendar",
    "interview.details": "Detalles de la entrevista",
    "interview.ready": "Todo listo",

    "common.cancel": "Cancelar",
  },

  // ── Mandarin Chinese (Simplified) ─────────────────────────────────────────
  zh: {
    "nav.dashboard": "控制台",
    "nav.postjob": "发布职位",
    "nav.browsejobs": "浏览工作",
    "nav.profile": "我的简历",
    "nav.logout": "退出登录",
    "nav.login": "登录",
    "nav.signup": "注册",

    "hero.title1": "为您的餐厅招募",
    "hero.title2": "优秀人才",
    "hero.subtitle": "ENTR 连接移民餐厅与优秀工人 — 由 AI 驱动。",
    "hero.employer": "我要招聘",
    "hero.worker": "我要找工作",
    "hero.feature1.title": "AI 筛选",
    "hero.feature1.desc": "每份申请都会自动评分，让您第一时间看到最佳匹配。",
    "hero.feature2.title": "多语言支持",
    "hero.feature2.desc": "平台支持 6 种语言 — 无语言障碍。",
    "hero.feature3.title": "快速简单",
    "hero.feature3.desc": "一分钟内发布工作。几步即可完成申请。",

    "landing.whyTitle": "专为努力工作的餐厅老板打造",
    "landing.howTitle": "三步完成招聘",
    "landing.step1.title": "发布职位",
    "landing.step1.desc": "描述职位、薪资和工作时间，仅需约 60 秒。",
    "landing.step2.title": "工人申请",
    "landing.step2.desc": "来自您所在地区的合格候选人直接申请。",
    "landing.step3.title": "AI 排名",
    "landing.step3.desc": "Claude AI 为每份申请评分，并为您提供清晰摘要。",
    "landing.cta.title": "准备好找到您的下一位优秀员工了吗？",
    "landing.cta.sub": "完全免费，无需信用卡。",
    "landing.cta.employer": "立即发布职位",
    "landing.cta.worker": "寻找工作",

    "signup.title": "创建您的账户",
    "signup.subtitle": "加入 ENTR — 完全免费。",
    "signup.name": "姓名",
    "signup.email": "电子邮箱",
    "signup.password": "密码",
    "signup.phone": "电话（选填）",
    "signup.language": "首选语言",
    "signup.role": "我是...",
    "signup.employer.label": "餐厅老板",
    "signup.employer.desc": "我想招聘员工",
    "signup.worker.label": "求职者",
    "signup.worker.desc": "我在找工作",
    "signup.restaurant": "餐厅名称（选填）",
    "signup.submit": "创建账户",
    "signup.login": "已有账户？",

    "login.title": "欢迎回来",
    "login.subtitle": "登录您的 ENTR 账户。",
    "login.email": "电子邮箱",
    "login.password": "密码",
    "login.submit": "登录",
    "login.signup": "还没有账户？",

    "employer.dashboard.title": "您的职位",
    "employer.dashboard.subtitle": "管理您的职位列表。",
    "employer.postjob.btn": "发布职位",
    "employer.job.applications": "查看申请",
    "employer.job.close": "关闭职位",
    "employer.job.reopen": "重新开放",
    "employer.job.applicants": "位申请者",
    "employer.noJobs": "暂无发布的职位。",
    "employer.noJobs.desc": "发布您的第一个职位以开始收到申请。",

    "postjob.title": "发布职位",
    "postjob.subtitle": "填写以下信息以找到您的下一位团队成员。",
    "postjob.position": "职位 / 标题",
    "postjob.pay": "薪资",
    "postjob.pay.hint": "例如：$18/小时 或 $600/周",
    "postjob.hours": "工作时间",
    "postjob.hours.hint": "例如：全职、周末、周一至周五 9am–5pm",
    "postjob.experience": "所需经验（年）",
    "postjob.language": "语言偏好",
    "postjob.language.hint": "例如：西班牙语、英语、双语",
    "postjob.location": "工作地点",
    "postjob.description": "职位描述（选填）",
    "postjob.submit": "发布",

    "applications.title": "申请列表：",
    "applications.back": "返回控制台",
    "applications.noApps": "暂无申请。",
    "applications.noApps.desc": "当工人申请后，申请将在这里显示。",
    "applications.score": "AI 匹配分数",
    "applications.summary": "AI 总结",
    "applications.experience": "经验",
    "applications.languages": "语言",
    "applications.phone": "电话",
    "applications.coverletter": "求职信",
    "applications.status": "状态",
    "applications.updateStatus": "更新",

    "worker.dashboard.title": "我的申请",
    "worker.dashboard.subtitle": "跟踪您的工作申请状态。",
    "worker.browseBtn": "浏览空缺职位",
    "worker.noApps": "暂无申请。",
    "worker.noApps.desc": "浏览空缺职位并申请以开始。",

    "browse.title": "空缺职位",
    "browse.subtitle": "找到您的下一个机会。",
    "browse.apply": "立即申请",
    "browse.applied": "已申请",
    "browse.noJobs": "暂无空缺职位。",
    "browse.noJobs.desc": "请稍后再来查看新的工作机会。",
    "browse.pay": "薪资",
    "browse.hours": "工作时间",
    "browse.experience": "经验",
    "browse.language": "语言",

    "apply.title": "申请职位：",
    "apply.coverletter": "求职信（选填）",
    "apply.coverletter.hint": "告诉雇主您为什么适合这份工作。",
    "apply.submit": "提交申请",
    "apply.back": "返回职位列表",

    "profile.title": "我的简历",
    "profile.subtitle": "保持简历更新以提高您的匹配分数。",
    "profile.bio": "技能与经验",
    "profile.bio.hint": "描述您的餐厅经验、技能以及您正在寻找的工作类型。",
    "profile.years": "工作经验（年）",
    "profile.languages": "会说的语言",
    "profile.languages.hint": "例如：英语、西班牙语、普通话",
    "profile.phone": "电话",
    "profile.save": "保存简历",

    "years.abbr": "年经验",
    "status.pending": "待处理",
    "status.reviewed": "已审查",
    "status.accepted": "已接受",
    "status.rejected": "已拒绝",
    "status.open": "开放中",
    "status.closed": "已关闭",
  },

  // ── French ────────────────────────────────────────────────────────────────
  fr: {
    "nav.dashboard": "Tableau de bord",
    "nav.postjob": "Publier un poste",
    "nav.browsejobs": "Parcourir les offres",
    "nav.profile": "Mon profil",
    "nav.logout": "Se déconnecter",
    "nav.login": "Se connecter",
    "nav.signup": "S'inscrire",

    "hero.title1": "Recrutez les meilleurs talents pour votre",
    "hero.title2": "restaurant",
    "hero.subtitle": "ENTR connecte les restaurants de propriétaires immigrés avec des travailleurs qualifiés, propulsé par l'IA.",
    "hero.employer": "Je recrute",
    "hero.worker": "Je cherche du travail",
    "hero.feature1.title": "Sélection par IA",
    "hero.feature1.desc": "Chaque candidature est notée automatiquement pour que vous voyiez les meilleures en premier.",
    "hero.feature2.title": "Multilingue",
    "hero.feature2.desc": "La plateforme fonctionne en 6 langues — sans barrière linguistique.",
    "hero.feature3.title": "Rapide et simple",
    "hero.feature3.desc": "Publiez un poste en moins d'une minute. Postulez en quelques clics.",

    "landing.whyTitle": "Conçu pour les restaurateurs qui travaillent dur",
    "landing.howTitle": "Recrutez en trois étapes simples",
    "landing.step1.title": "Publiez un poste",
    "landing.step1.desc": "Décrivez le rôle, le salaire et les horaires. Cela prend environ 60 secondes.",
    "landing.step2.title": "Les candidats postulent",
    "landing.step2.desc": "Des candidats qualifiés de votre région postulent directement.",
    "landing.step3.title": "L'IA les classe",
    "landing.step3.desc": "Claude AI note chaque candidature et vous donne un résumé clair.",
    "landing.cta.title": "Prêt à trouver votre prochain excellent employé ?",
    "landing.cta.sub": "Gratuit. Aucune carte de crédit requise.",
    "landing.cta.employer": "Publier un poste",
    "landing.cta.worker": "Trouver du travail",

    "signup.title": "Créer votre compte",
    "signup.subtitle": "Rejoignez ENTR — c'est gratuit.",
    "signup.name": "Nom complet",
    "signup.email": "Adresse e-mail",
    "signup.password": "Mot de passe",
    "signup.phone": "Téléphone (optionnel)",
    "signup.language": "Langue préférée",
    "signup.role": "Je suis...",
    "signup.employer.label": "Propriétaire de restaurant",
    "signup.employer.desc": "Je veux embaucher du personnel",
    "signup.worker.label": "Chercheur d'emploi",
    "signup.worker.desc": "Je cherche du travail",
    "signup.restaurant": "Nom du restaurant (optionnel)",
    "signup.submit": "Créer un compte",
    "signup.login": "Vous avez déjà un compte ?",

    "login.title": "Bon retour",
    "login.subtitle": "Connectez-vous à votre compte ENTR.",
    "login.email": "Adresse e-mail",
    "login.password": "Mot de passe",
    "login.submit": "Se connecter",
    "login.signup": "Vous n'avez pas de compte ?",

    "employer.dashboard.title": "Vos offres d'emploi",
    "employer.dashboard.subtitle": "Gérez vos annonces d'emploi.",
    "employer.postjob.btn": "Publier un poste",
    "employer.job.applications": "Voir les candidatures",
    "employer.job.close": "Fermer l'offre",
    "employer.job.reopen": "Rouvrir",
    "employer.job.applicants": "candidats",
    "employer.noJobs": "Aucune offre publiée.",
    "employer.noJobs.desc": "Publiez votre première offre pour recevoir des candidatures.",

    "postjob.title": "Publier un poste",
    "postjob.subtitle": "Remplissez les détails pour trouver votre prochain collaborateur.",
    "postjob.position": "Poste / Titre",
    "postjob.pay": "Salaire",
    "postjob.pay.hint": "ex. 18 €/h ou 600 €/semaine",
    "postjob.hours": "Horaires",
    "postjob.hours.hint": "ex. Temps plein, Week-ends, Lun–Ven 9h–17h",
    "postjob.experience": "Expérience requise (années)",
    "postjob.language": "Préférence linguistique",
    "postjob.language.hint": "ex. Espagnol, Anglais, Bilingue",
    "postjob.location": "Lieu",
    "postjob.description": "Description du poste (optionnel)",
    "postjob.submit": "Publier",

    "applications.title": "Candidatures pour",
    "applications.back": "Retour au tableau de bord",
    "applications.noApps": "Aucune candidature pour l'instant.",
    "applications.noApps.desc": "Les candidatures apparaîtront ici lorsque des travailleurs postuleront.",
    "applications.score": "Score IA",
    "applications.summary": "Résumé IA",
    "applications.experience": "Expérience",
    "applications.languages": "Langues",
    "applications.phone": "Téléphone",
    "applications.coverletter": "Lettre de motivation",
    "applications.status": "Statut",
    "applications.updateStatus": "Mettre à jour",

    "worker.dashboard.title": "Mes candidatures",
    "worker.dashboard.subtitle": "Suivez le statut de vos candidatures.",
    "worker.browseBtn": "Voir les offres disponibles",
    "worker.noApps": "Aucune candidature pour l'instant.",
    "worker.noApps.desc": "Parcourez les offres disponibles et postulez pour commencer.",

    "browse.title": "Offres disponibles",
    "browse.subtitle": "Trouvez votre prochaine opportunité.",
    "browse.apply": "Postuler",
    "browse.applied": "Déjà postulé",
    "browse.noJobs": "Aucune offre ouverte pour l'instant.",
    "browse.noJobs.desc": "Revenez bientôt pour de nouvelles opportunités.",
    "browse.pay": "Salaire",
    "browse.hours": "Horaires",
    "browse.experience": "Expérience",
    "browse.language": "Langue",

    "apply.title": "Postuler pour",
    "apply.coverletter": "Lettre de motivation (optionnel)",
    "apply.coverletter.hint": "Expliquez à l'employeur pourquoi vous êtes le candidat idéal.",
    "apply.submit": "Envoyer ma candidature",
    "apply.back": "Retour aux offres",

    "profile.title": "Mon profil",
    "profile.subtitle": "Gardez votre profil à jour pour améliorer votre score de correspondance.",
    "profile.bio": "Compétences et expérience",
    "profile.bio.hint": "Décrivez votre expérience en restauration, vos compétences et le type de travail que vous recherchez.",
    "profile.years": "Années d'expérience",
    "profile.languages": "Langues parlées",
    "profile.languages.hint": "ex. Anglais, Espagnol, Mandarin",
    "profile.phone": "Téléphone",
    "profile.save": "Enregistrer le profil",

    "years.abbr": "ans d'exp.",
    "status.pending": "En attente",
    "status.reviewed": "Examiné",
    "status.accepted": "Accepté",
    "status.rejected": "Refusé",
    "status.open": "Ouvert",
    "status.closed": "Fermé",
  },

  // ── Portuguese (Brazilian) ────────────────────────────────────────────────
  pt: {
    "nav.dashboard": "Painel",
    "nav.postjob": "Publicar vaga",
    "nav.browsejobs": "Ver vagas",
    "nav.profile": "Meu perfil",
    "nav.logout": "Sair",
    "nav.login": "Entrar",
    "nav.signup": "Cadastrar",

    "hero.title1": "Contrate os melhores talentos para o seu",
    "hero.title2": "restaurante",
    "hero.subtitle": "A ENTR conecta restaurantes de proprietários imigrantes com trabalhadores qualificados, com IA.",
    "hero.employer": "Quero contratar",
    "hero.worker": "Estou procurando emprego",
    "hero.feature1.title": "Triagem por IA",
    "hero.feature1.desc": "Cada candidatura é pontuada automaticamente para que você veja as melhores primeiro.",
    "hero.feature2.title": "Multilíngue",
    "hero.feature2.desc": "A plataforma funciona em 6 idiomas — sem barreiras de idioma.",
    "hero.feature3.title": "Rápido e simples",
    "hero.feature3.desc": "Publique uma vaga em menos de um minuto. Candidate-se com poucos cliques.",

    "landing.whyTitle": "Feito para donos de restaurante que trabalham duro",
    "landing.howTitle": "Contrate em três etapas simples",
    "landing.step1.title": "Publique uma vaga",
    "landing.step1.desc": "Descreva o cargo, salário e horário. Leva cerca de 60 segundos.",
    "landing.step2.title": "Candidatos aplicam",
    "landing.step2.desc": "Candidatos qualificados da sua região se candidatam diretamente.",
    "landing.step3.title": "A IA classifica",
    "landing.step3.desc": "Claude AI pontua cada candidatura e fornece um resumo claro.",
    "landing.cta.title": "Pronto para encontrar seu próximo grande funcionário?",
    "landing.cta.sub": "Gratuito. Sem cartão de crédito.",
    "landing.cta.employer": "Publicar vaga agora",
    "landing.cta.worker": "Buscar trabalho",

    "signup.title": "Criar sua conta",
    "signup.subtitle": "Junte-se à ENTR — é gratuito.",
    "signup.name": "Nome completo",
    "signup.email": "E-mail",
    "signup.password": "Senha",
    "signup.phone": "Telefone (opcional)",
    "signup.language": "Idioma preferido",
    "signup.role": "Eu sou...",
    "signup.employer.label": "Dono de restaurante",
    "signup.employer.desc": "Quero contratar funcionários",
    "signup.worker.label": "Candidato a emprego",
    "signup.worker.desc": "Estou procurando trabalho",
    "signup.restaurant": "Nome do restaurante (opcional)",
    "signup.submit": "Criar conta",
    "signup.login": "Já tem uma conta?",

    "login.title": "Bem-vindo de volta",
    "login.subtitle": "Entre na sua conta ENTR.",
    "login.email": "E-mail",
    "login.password": "Senha",
    "login.submit": "Entrar",
    "login.signup": "Não tem uma conta?",

    "employer.dashboard.title": "Suas vagas",
    "employer.dashboard.subtitle": "Gerencie suas ofertas de emprego.",
    "employer.postjob.btn": "Publicar vaga",
    "employer.job.applications": "Ver candidaturas",
    "employer.job.close": "Encerrar vaga",
    "employer.job.reopen": "Reabrir",
    "employer.job.applicants": "candidatos",
    "employer.noJobs": "Nenhuma vaga publicada.",
    "employer.noJobs.desc": "Publique sua primeira vaga para receber candidaturas.",

    "postjob.title": "Publicar vaga",
    "postjob.subtitle": "Preencha os detalhes para encontrar seu próximo colaborador.",
    "postjob.position": "Cargo / Título",
    "postjob.pay": "Salário",
    "postjob.pay.hint": "ex. R$20/h ou R$2.000/semana",
    "postjob.hours": "Horário",
    "postjob.hours.hint": "ex. Tempo integral, Fins de semana, Seg–Sex 9h–17h",
    "postjob.experience": "Experiência necessária (anos)",
    "postjob.language": "Preferência de idioma",
    "postjob.language.hint": "ex. Espanhol, Inglês, Bilíngue",
    "postjob.location": "Localização",
    "postjob.description": "Descrição da vaga (opcional)",
    "postjob.submit": "Publicar",

    "applications.title": "Candidaturas para",
    "applications.back": "Voltar ao painel",
    "applications.noApps": "Nenhuma candidatura ainda.",
    "applications.noApps.desc": "As candidaturas aparecerão aqui quando os trabalhadores se candidatarem.",
    "applications.score": "Pontuação IA",
    "applications.summary": "Resumo IA",
    "applications.experience": "Experiência",
    "applications.languages": "Idiomas",
    "applications.phone": "Telefone",
    "applications.coverletter": "Carta de apresentação",
    "applications.status": "Status",
    "applications.updateStatus": "Atualizar",

    "worker.dashboard.title": "Minhas candidaturas",
    "worker.dashboard.subtitle": "Acompanhe o status das suas candidaturas.",
    "worker.browseBtn": "Ver vagas disponíveis",
    "worker.noApps": "Nenhuma candidatura ainda.",
    "worker.noApps.desc": "Veja as vagas disponíveis e candidate-se para começar.",

    "browse.title": "Vagas disponíveis",
    "browse.subtitle": "Encontre sua próxima oportunidade.",
    "browse.apply": "Candidatar-se",
    "browse.applied": "Já candidatou",
    "browse.noJobs": "Nenhuma vaga aberta agora.",
    "browse.noJobs.desc": "Volte em breve para novas oportunidades.",
    "browse.pay": "Salário",
    "browse.hours": "Horário",
    "browse.experience": "Experiência",
    "browse.language": "Idioma",

    "apply.title": "Candidatar-se para",
    "apply.coverletter": "Carta de apresentação (opcional)",
    "apply.coverletter.hint": "Conte ao empregador por que você seria perfeito para a vaga.",
    "apply.submit": "Enviar candidatura",
    "apply.back": "Voltar para vagas",

    "profile.title": "Meu perfil",
    "profile.subtitle": "Mantenha seu perfil atualizado para melhorar sua pontuação de compatibilidade.",
    "profile.bio": "Habilidades e experiência",
    "profile.bio.hint": "Descreva sua experiência em restaurantes, habilidades e o tipo de trabalho que procura.",
    "profile.years": "Anos de experiência",
    "profile.languages": "Idiomas falados",
    "profile.languages.hint": "ex. Inglês, Espanhol, Mandarim",
    "profile.phone": "Telefone",
    "profile.save": "Salvar perfil",

    "years.abbr": "anos exp.",
    "status.pending": "Pendente",
    "status.reviewed": "Revisado",
    "status.accepted": "Aceito",
    "status.rejected": "Rejeitado",
    "status.open": "Aberta",
    "status.closed": "Encerrada",
  },

  // ── Vietnamese ────────────────────────────────────────────────────────────
  vi: {
    "nav.dashboard": "Bảng điều khiển",
    "nav.postjob": "Đăng tuyển dụng",
    "nav.browsejobs": "Tìm việc làm",
    "nav.profile": "Hồ sơ của tôi",
    "nav.logout": "Đăng xuất",
    "nav.login": "Đăng nhập",
    "nav.signup": "Đăng ký",

    "hero.title1": "Tuyển dụng nhân tài cho",
    "hero.title2": "nhà hàng của bạn",
    "hero.subtitle": "ENTR kết nối nhà hàng của người nhập cư với những người lao động có năng lực, được hỗ trợ bởi AI.",
    "hero.employer": "Tôi muốn tuyển dụng",
    "hero.worker": "Tôi đang tìm việc",
    "hero.feature1.title": "Sàng lọc AI",
    "hero.feature1.desc": "Mỗi đơn xin việc được chấm điểm tự động để bạn thấy những ứng viên phù hợp nhất trước.",
    "hero.feature2.title": "Đa ngôn ngữ",
    "hero.feature2.desc": "Nền tảng hoạt động bằng 6 ngôn ngữ — không có rào cản ngôn ngữ.",
    "hero.feature3.title": "Nhanh chóng và đơn giản",
    "hero.feature3.desc": "Đăng tin tuyển dụng trong chưa đầy một phút. Nộp đơn chỉ với vài bước.",

    "landing.whyTitle": "Xây dựng cho chủ nhà hàng làm việc chăm chỉ",
    "landing.howTitle": "Tuyển dụng trong ba bước đơn giản",
    "landing.step1.title": "Đăng tin tuyển dụng",
    "landing.step1.desc": "Mô tả vị trí, mức lương và giờ làm việc. Chỉ mất khoảng 60 giây.",
    "landing.step2.title": "Người lao động ứng tuyển",
    "landing.step2.desc": "Ứng viên có năng lực từ khu vực của bạn ứng tuyển trực tiếp.",
    "landing.step3.title": "AI xếp hạng",
    "landing.step3.desc": "Claude AI chấm điểm từng đơn ứng tuyển và cung cấp tóm tắt rõ ràng.",
    "landing.cta.title": "Sẵn sàng tìm nhân viên xuất sắc tiếp theo chưa?",
    "landing.cta.sub": "Hoàn toàn miễn phí. Không cần thẻ tín dụng.",
    "landing.cta.employer": "Đăng tin ngay",
    "landing.cta.worker": "Tìm việc làm",

    "signup.title": "Tạo tài khoản của bạn",
    "signup.subtitle": "Tham gia ENTR — hoàn toàn miễn phí.",
    "signup.name": "Họ và tên",
    "signup.email": "Email",
    "signup.password": "Mật khẩu",
    "signup.phone": "Điện thoại (tùy chọn)",
    "signup.language": "Ngôn ngữ ưa thích",
    "signup.role": "Tôi là...",
    "signup.employer.label": "Chủ nhà hàng",
    "signup.employer.desc": "Tôi muốn tuyển dụng nhân viên",
    "signup.worker.label": "Người tìm việc",
    "signup.worker.desc": "Tôi đang tìm việc làm",
    "signup.restaurant": "Tên nhà hàng (tùy chọn)",
    "signup.submit": "Tạo tài khoản",
    "signup.login": "Đã có tài khoản?",

    "login.title": "Chào mừng trở lại",
    "login.subtitle": "Đăng nhập vào tài khoản ENTR của bạn.",
    "login.email": "Email",
    "login.password": "Mật khẩu",
    "login.submit": "Đăng nhập",
    "login.signup": "Chưa có tài khoản?",

    "employer.dashboard.title": "Tin tuyển dụng của bạn",
    "employer.dashboard.subtitle": "Quản lý các tin đăng tuyển dụng.",
    "employer.postjob.btn": "Đăng tuyển dụng",
    "employer.job.applications": "Xem đơn ứng tuyển",
    "employer.job.close": "Đóng tin tuyển dụng",
    "employer.job.reopen": "Mở lại",
    "employer.job.applicants": "ứng viên",
    "employer.noJobs": "Chưa có tin tuyển dụng nào.",
    "employer.noJobs.desc": "Đăng tin tuyển dụng đầu tiên để nhận đơn ứng tuyển.",

    "postjob.title": "Đăng tin tuyển dụng",
    "postjob.subtitle": "Điền thông tin để tìm nhân viên tiếp theo của bạn.",
    "postjob.position": "Vị trí / Chức danh",
    "postjob.pay": "Lương",
    "postjob.pay.hint": "vd. $18/giờ hoặc $600/tuần",
    "postjob.hours": "Giờ làm việc",
    "postjob.hours.hint": "vd. Toàn thời gian, Cuối tuần, T2–T6 9h–17h",
    "postjob.experience": "Kinh nghiệm yêu cầu (năm)",
    "postjob.language": "Ưu tiên ngôn ngữ",
    "postjob.language.hint": "vd. Tiếng Tây Ban Nha, Tiếng Anh, Song ngữ",
    "postjob.location": "Địa điểm",
    "postjob.description": "Mô tả công việc (tùy chọn)",
    "postjob.submit": "Đăng tin",

    "applications.title": "Đơn ứng tuyển cho",
    "applications.back": "Quay lại bảng điều khiển",
    "applications.noApps": "Chưa có đơn ứng tuyển nào.",
    "applications.noApps.desc": "Đơn ứng tuyển sẽ xuất hiện tại đây khi người lao động nộp đơn.",
    "applications.score": "Điểm AI",
    "applications.summary": "Tóm tắt AI",
    "applications.experience": "Kinh nghiệm",
    "applications.languages": "Ngôn ngữ",
    "applications.phone": "Điện thoại",
    "applications.coverletter": "Thư xin việc",
    "applications.status": "Trạng thái",
    "applications.updateStatus": "Cập nhật",

    "worker.dashboard.title": "Đơn ứng tuyển của tôi",
    "worker.dashboard.subtitle": "Theo dõi trạng thái đơn ứng tuyển của bạn.",
    "worker.browseBtn": "Xem việc làm hiện có",
    "worker.noApps": "Chưa có đơn ứng tuyển nào.",
    "worker.noApps.desc": "Xem các việc làm hiện có và nộp đơn để bắt đầu.",

    "browse.title": "Việc làm hiện có",
    "browse.subtitle": "Tìm cơ hội tiếp theo của bạn.",
    "browse.apply": "Ứng tuyển ngay",
    "browse.applied": "Đã ứng tuyển",
    "browse.noJobs": "Hiện không có việc làm nào.",
    "browse.noJobs.desc": "Quay lại sớm để xem cơ hội mới.",
    "browse.pay": "Lương",
    "browse.hours": "Giờ làm",
    "browse.experience": "Kinh nghiệm",
    "browse.language": "Ngôn ngữ",

    "apply.title": "Ứng tuyển vào",
    "apply.coverletter": "Thư xin việc (tùy chọn)",
    "apply.coverletter.hint": "Hãy cho nhà tuyển dụng biết tại sao bạn phù hợp với vị trí này.",
    "apply.submit": "Gửi đơn ứng tuyển",
    "apply.back": "Quay lại danh sách việc",

    "profile.title": "Hồ sơ của tôi",
    "profile.subtitle": "Cập nhật hồ sơ để cải thiện điểm phù hợp của bạn.",
    "profile.bio": "Kỹ năng và kinh nghiệm",
    "profile.bio.hint": "Mô tả kinh nghiệm nhà hàng, kỹ năng và loại công việc bạn đang tìm kiếm.",
    "profile.years": "Số năm kinh nghiệm",
    "profile.languages": "Ngôn ngữ nói được",
    "profile.languages.hint": "vd. Tiếng Anh, Tiếng Tây Ban Nha, Tiếng Quan Thoại",
    "profile.phone": "Điện thoại",
    "profile.save": "Lưu hồ sơ",

    "years.abbr": "năm kinh nghiệm",
    "status.pending": "Đang chờ",
    "status.reviewed": "Đã xem xét",
    "status.accepted": "Đã chấp nhận",
    "status.rejected": "Đã từ chối",
    "status.open": "Đang mở",
    "status.closed": "Đã đóng",
  },
};

// ── i18n engine ───────────────────────────────────────────────────────────────

function getLang() {
  return document.documentElement.lang || "en";
}

function t(key) {
  const lang = getLang();
  const dict = TRANSLATIONS[lang] || TRANSLATIONS["en"];
  return dict[key] !== undefined ? dict[key] : (TRANSLATIONS["en"][key] || key);
}

function applyTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.getAttribute("data-i18n-placeholder"));
  });
}

// ── Language dropdown ─────────────────────────────────────────────────────────

function initLangDropdown() {
  const sel = document.getElementById("lang-select");
  if (!sel) return;
  sel.addEventListener("change", () => {
    window.location.href = "/set-language/" + sel.value;
  });
}

// ── Role card selection ───────────────────────────────────────────────────────

function initRoleSelector() {
  document.querySelectorAll(".role-card").forEach((card) => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".role-card").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
      card.querySelector("input[type='radio']").checked = true;

      const isEmployer = card.querySelector("input").value === "employer";
      const restaurantField = document.getElementById("restaurant-field");
      if (restaurantField) restaurantField.style.display = isEmployer ? "block" : "none";
    });
  });
  const first = document.querySelector(".role-card");
  if (first) first.click();
}

// ── Tabbed feature section (Why ENTR) ────────────────────────────────────────

function initFeatureTabs() {
  const btns = document.querySelectorAll(".tab-btn[data-tab]");
  if (!btns.length) return;

  function activate(btn) {
    const target = btn.dataset.tab;
    btns.forEach((b) => {
      b.classList.toggle("active", b === btn);
      b.setAttribute("aria-selected", b === btn ? "true" : "false");
    });
    document.querySelectorAll(".tab-panel[data-panel]").forEach((p) => {
      p.classList.toggle("active", p.dataset.panel === target);
    });
  }

  btns.forEach((btn) => btn.addEventListener("click", () => activate(btn)));
}

// ── Sticky nav frosted glass ──────────────────────────────────────────────────

function initStickyNav() {
  const nav = document.querySelector("nav");
  if (!nav) return;
  const toggle = () => nav.classList.toggle("nav-scrolled", window.scrollY > 48);
  window.addEventListener("scroll", toggle, { passive: true });
  toggle();
}

// ── Scroll reveal ─────────────────────────────────────────────────────────────

function initScrollAnimations() {
  const els = document.querySelectorAll("[data-animate]");
  if (!els.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -32px 0px" }
  );

  els.forEach((el) => observer.observe(el));
}

// ── Role tabs (new signup page) ───────────────────────────────────────────────

function initRoleTabs() {
  const tabs = document.querySelectorAll(".role-tab");
  if (!tabs.length) return;

  function selectRole(role) {
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.role === role));
    const roleInput = document.getElementById("role-input");
    if (roleInput) roleInput.value = role;
    document.querySelectorAll("[data-role-fields]").forEach((section) => {
      section.style.display = section.dataset.roleFields === role ? "block" : "none";
    });
  }

  tabs.forEach((tab) => tab.addEventListener("click", () => selectRole(tab.dataset.role)));

  const urlRole = new URLSearchParams(window.location.search).get("role");
  selectRole(urlRole === "worker" ? "worker" : "employer");
}

// ── Score colour ──────────────────────────────────────────────────────────────

function initScores() {
  document.querySelectorAll(".score-circle[data-score]").forEach((el) => {
    const s = parseInt(el.dataset.score, 10);
    el.classList.add(s >= 70 ? "score-high" : s >= 45 ? "score-mid" : "score-low");
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  applyTranslations();
  initLangDropdown();
  initRoleSelector();
  initRoleTabs();
  initScores();
  initScrollAnimations();
  initStickyNav();
  initFeatureTabs();
});
