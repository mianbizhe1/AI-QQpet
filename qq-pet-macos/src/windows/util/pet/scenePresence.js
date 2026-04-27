(() => {
  const _require = eval("require");
  const https = _require("https");
  const http = _require("http");
  const fs = _require("fs");
  const path = _require("path");
  const { app } = _require("electron");
  const { pathToFileURL } = _require("url");
  let screenshotTools = {};

  try {
    screenshotTools = _require("../screenshot");
  } catch (error) {
    screenshotTools = {};
  }

  const MINIMAX_IMAGE_URL = "https://api.minimaxi.com/v1/image_generation";

  const destinations = [
    {
      key: "paris",
      name: "巴黎明信片",
      icon: "../assets/Background/b0000008.png",
      prompt: "在巴黎埃菲尔铁塔前拍一张旅行明信片",
      scene: "Eiffel Tower, Paris, golden hour, travel postcard",
    },
    {
      key: "kyoto",
      name: "京都樱花",
      icon: "../assets/Background/b0000010.png",
      prompt: "在京都樱花小路拍一张旅行照",
      scene: "Kyoto cherry blossom street, spring, soft sunlight",
    },
    {
      key: "aurora",
      name: "极光露营",
      icon: "../assets/Background/b0000014.png",
      prompt: "在北欧极光下露营自拍",
      scene: "Nordic aurora, cozy campsite, night sky",
    },
    {
      key: "memoir",
      name: "生活漫画",
      icon: "../assets/Background/b0000003.png",
      prompt: "把主人当前的生活片段画成漫画回忆录",
      scene: "warm comic memoir panel, everyday life, cozy desktop companion",
      memoir: true,
    },
  ];

  function getTripScenes() {
    return destinations.map((item) => ({
      ...item,
      type: "trip",
      valueList: {
        desc: { label: "跨场景：", value: item.prompt },
        tip: { label: "操作：", value: "点击生成 AIGC 照片" },
      },
    }));
  }

  function getLifeAlbumScenes() {
    const today = new Date();
    const period = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");

    return [
      {
        key: "daily-review",
        name: "今日回顾",
        icon: "../assets/Background/b0000003.png",
        type: "album",
        granularity: "day",
        period,
        valueList: {
          desc: { label: "回顾：", value: "把今天主人和小Q的互动画成回忆相册" },
          tip: { label: "操作：", value: "点击生成以互动为主的今日漫画回顾" },
          date: { label: "日期：", value: period },
        },
      },
    ];
  }

  async function generateSceneImage(option = {}, petInfo = {}) {
    const apiKey = getConfiguredApiKey();
    if (!apiKey) {
      throw new Error("未配置 llm.api_key，无法生成跨场景照片");
    }

    const prompt = await buildPrompt(option, petInfo);
    const payload = {
      model: "image-01",
      prompt,
      aspect_ratio: "16:9",
      response_format: "base64",
    };

    const subjectReference = process.env.MINIMAX_QQPET_REFERENCE_URL;
    if (subjectReference) {
      payload.subject_reference = [
        {
          type: "character",
          image_file: subjectReference,
        },
      ];
    }

    const response = await postJson(MINIMAX_IMAGE_URL, apiKey, payload);
    const imageBase64 = response?.data?.image_base64?.[0];
    if (!imageBase64) {
      throw new Error("图片生成失败：MiniMax 未返回图片");
    }

    const saved = saveImage(imageBase64, option.key || "scene");
    return {
      ...saved,
      prompt,
      message: option.memoir
        ? "我把你的生活片段画成漫画回忆录啦～"
        : `我从${option.name || "远方"}寄回一张旅行照啦～`,
    };
  }

  async function generateLifeAlbumImage(option = {}, petInfo = {}) {
    const apiKey = getConfiguredApiKey();
    if (!apiKey) {
      throw new Error("未配置 llm.api_key，无法生成生活相册图");
    }

    const granularity = option.granularity || "day";
    const period = option.period || "";
    const payload = await fetchAlbumPayload({ granularity, period, limit: option.limit || 50 });

    if (!payload?.count) {
      throw new Error(`当前${granularity}维度暂无可用生活记录`);
    }

    const body = {
      model: "image-01",
      prompt: payload.prompt,
      aspect_ratio: "16:9",
      response_format: "base64",
    };

    const response = await postJson(MINIMAX_IMAGE_URL, apiKey, body);
    const imageBase64 = response?.data?.image_base64?.[0];
    if (!imageBase64) {
      throw new Error("图片生成失败：MiniMax 未返回图片");
    }

    const saved = saveAlbumImage(imageBase64, payload);
    return {
      ...saved,
      prompt: payload.prompt,
      granularity,
      period: payload.period,
      count: payload.count,
      records: payload.records || [],
      album_output_path: payload.album_output_path,
      message: `我把这段${formatGranularityLabel(granularity)}生活整理成漫画相册啦～`,
    };
  }

  async function buildPrompt(option, petInfo) {
    const host = petInfo?.info?.host || "主人";
    let lifeContext = "";
    let memoryContext = "";

    if (option.memoir && screenshotTools.captureScreen) {
      try {
        const screen = await screenshotTools.captureScreen();
        if (screen?.frontmost_app || screen?.frontmost_window) {
          lifeContext = ` The owner is currently around ${screen.frontmost_app || "their computer"}${screen.frontmost_window ? `, window title: ${screen.frontmost_window}` : ""}.`;
        }
      } catch (error) {
        lifeContext = "";
      }
    }

    if (option.memoir) {
      memoryContext = await buildMemoryContext(option, lifeContext);
    }

    return [
      "A cute QQ Pet style penguin companion, black and white body, big round eyes, orange beak and feet, blue scarf, yellow star pendant.",
      option.memoir
        ? `Create a warm four-panel comic memoir about ${host}'s everyday life with this penguin companion.${lifeContext}${memoryContext}`
        : `Create a photorealistic virtual travel photo of the penguin at ${option.scene || option.prompt}.`,
      "Keep the character recognizable, charming, friendly, full-body visible, cinematic composition, high quality, no text, no watermark.",
    ].join(" ");
  }

  async function buildMemoryContext(option, lifeContext) {
    const localMemory = getLocalMemoryContext();
    const backendMemory = await getBackendMemoryContext(option, lifeContext, localMemory);
    const parts = [];

    if (localMemory.recent.length) {
      parts.push(`Recent conversations/events: ${localMemory.recent.join("; ")}.`);
    }
    if (localMemory.important.length) {
      parts.push(`Important memories: ${localMemory.important.join("; ")}.`);
    }
    if (backendMemory.length) {
      parts.push(`Long-term recalled memories: ${backendMemory.join("; ")}.`);
    }

    return parts.length
      ? ` Use these memory hints as visual story inspiration, without rendering text: ${parts.join(" ")}`
      : "";
  }

  function getLocalMemoryContext() {
    const memory = global.aiBrainInstance?.memory;
    if (!memory) return { recent: [], important: [] };

    const recent = safeCall(() => memory.getRecentInteractions(6), [])
      .map(formatMemoryItem)
      .filter(Boolean)
      .slice(0, 6);
    const important = safeCall(() => memory.getMidTerm(5), [])
      .concat(safeCall(() => memory.getDerivedHints(3), []))
      .map(formatMemoryItem)
      .filter(Boolean)
      .slice(0, 5);

    return { recent, important };
  }

  async function getBackendMemoryContext(option, lifeContext, localMemory) {
    const brain = global.aiBrainInstance;
    if (!brain?.httpJson) return [];

    try {
      const topic = [
        option.prompt,
        lifeContext,
        ...localMemory.recent.slice(0, 3),
        ...localMemory.important.slice(0, 3),
      ].filter(Boolean).join(" ");
      const result = await brain.httpJson("POST", "/memory/recall", {
        context: {
          current_topic: topic || "生活漫画 回忆录 主人最近的话题",
          purpose: "comic_memoir_scene_generation",
          emotional_state: "warm",
          tags: ["生活漫画", "回忆录", "跨场景存在"],
        },
        limit: 5,
        personality: brain.memory?.personality || {},
      });
      return (result?.memories || [])
        .map((item) => item?.memory?.content || item?.content || "")
        .filter(Boolean)
        .map(trimMemoryText)
        .slice(0, 5);
    } catch (error) {
      console.warn("[scenePresence] backend memory recall failed:", error);
      return [];
    }
  }

  function formatMemoryItem(item) {
    if (!item) return "";
    return trimMemoryText(item.content || item.message || item.text || item.type || "");
  }

  function trimMemoryText(text) {
    return String(text || "").replace(/\s+/g, " ").trim().slice(0, 90);
  }

  function safeCall(fn, fallback) {
    try {
      return fn() || fallback;
    } catch (error) {
      return fallback;
    }
  }

  function postJson(url, apiKey, payload) {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify(payload);
      const request = https.request(
        url,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(body),
          },
        },
        (response) => {
          let raw = "";
          response.setEncoding("utf8");
          response.on("data", (chunk) => {
            raw += chunk;
          });
          response.on("end", () => {
            let parsed = {};
            try {
              parsed = raw ? JSON.parse(raw) : {};
            } catch (error) {
              reject(new Error(`MiniMax 返回解析失败：${raw.slice(0, 120)}`));
              return;
            }
            if (response.statusCode < 200 || response.statusCode >= 300) {
              reject(new Error(parsed?.message || parsed?.error?.message || `MiniMax 请求失败：HTTP ${response.statusCode}`));
              return;
            }
            resolve(parsed);
          });
        }
      );

      request.setTimeout(90000, () => {
        request.destroy(new Error("图片生成超时，请稍后重试"));
      });
      request.on("error", reject);
      request.write(body);
      request.end();
    });
  }

  function saveImage(imageBase64, key) {
    const dir = path.join(app.getPath("userData"), "scene-presence");
    fs.mkdirSync(dir, { recursive: true });
    const filename = `${Date.now()}-${String(key).replace(/[^\w-]/g, "")}.jpeg`;
    const filepath = path.join(dir, filename);
    fs.writeFileSync(filepath, Buffer.from(imageBase64, "base64"));
    return {
      filepath,
      fileUrl: pathToFileURL(filepath).toString(),
      dataUrl: `data:image/jpeg;base64,${imageBase64}`,
    };
  }

  function saveAlbumImage(imageBase64, payload) {
    const targetPath = payload?.album_output_path;
    if (!targetPath) {
      return saveImage(imageBase64, `album-${payload?.granularity || "day"}`);
    }

    const dir = path.dirname(targetPath);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(targetPath, Buffer.from(imageBase64, "base64"));
    return {
      filepath: targetPath,
      fileUrl: pathToFileURL(targetPath).toString(),
      dataUrl: `data:image/jpeg;base64,${imageBase64}`,
    };
  }

  function fetchAlbumPayload(payload) {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify(payload || {});
      const request = http.request(
        {
          hostname: "127.0.0.1",
          port: 18080,
          path: "/life-album/render",
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(body),
          },
        },
        (response) => {
          let raw = "";
          response.setEncoding("utf8");
          response.on("data", (chunk) => {
            raw += chunk;
          });
          response.on("end", () => {
            try {
              const parsed = raw ? JSON.parse(raw) : {};
              if (response.statusCode < 200 || response.statusCode >= 300) {
                reject(new Error(parsed?.error || `生活相册请求失败：HTTP ${response.statusCode}`));
                return;
              }
              resolve(parsed);
            } catch (error) {
              reject(error);
            }
          });
        }
      );

      request.setTimeout(30000, () => {
        request.destroy(new Error("生活相册请求超时"));
      });
      request.on("error", reject);
      request.write(body);
      request.end();
    });
  }

  function formatGranularityLabel(granularity) {
    const labels = {
      capture: "单次",
      day: "一天",
      week: "一周",
      month: "一个月",
    };
    return labels[granularity] || granularity;
  }

  function getConfiguredApiKey() {
    // 尝试加载 .env 文件
    const envPaths = [
      path.join(app.getPath("userData"), "ai-backend", ".env"),
      path.resolve(__dirname, "../../../../../.env"),
    ];
    try {
      for (const envPath of envPaths) {
        if (!fs.existsSync(envPath)) continue;
        const envContent = fs.readFileSync(envPath, "utf8");
        envContent.split(/\r?\n/).forEach(line => {
          const match = line.match(/^([^=]+)=(.*)$/);
          if (match) {
            process.env[match[1].trim()] = match[2].trim();
          }
        });
      }
    } catch (e) {}

    return (
      process.env.MINIMAX_API_KEY ||
      process.env.LLM_API_KEY ||
      readLlmApiKeyFromConfig() ||
      ""
    );
  }

  function readLlmApiKeyFromConfig() {
    const configPaths = [
      path.join(app.getPath("userData"), "ai-backend", "config.yaml"),
      path.resolve(__dirname, "../../../../../src/ai_llm/config.yaml"),
      path.resolve(__dirname, "../../../../../config.yaml"),
      path.resolve(process.cwd(), "src/ai_llm/config.yaml"),
      path.resolve(process.cwd(), "config.yaml"),
    ];

    for (const configPath of configPaths) {
      try {
        if (!fs.existsSync(configPath)) continue;
        const apiKey = parseNestedYamlValue(fs.readFileSync(configPath, "utf8"), "llm", "api_key");
        if (apiKey) return apiKey;
      } catch (error) {}
    }
    return "";
  }

  function parseNestedYamlValue(content, section, key) {
    const lines = String(content || "").split(/\r?\n/);
    let inSection = false;
    let sectionIndent = -1;

    for (const line of lines) {
      if (!line.trim() || line.trim().startsWith("#")) continue;
      const indent = line.match(/^\s*/)[0].length;
      const trimmed = line.trim();

      if (!inSection && trimmed === `${section}:`) {
        inSection = true;
        sectionIndent = indent;
        continue;
      }

      if (inSection && indent <= sectionIndent) {
        inSection = false;
      }

      if (inSection) {
        const match = trimmed.match(new RegExp(`^${key}:\\s*(.*)$`));
        if (match) return unquoteYamlScalar(match[1]);
      }
    }
    return "";
  }

  function unquoteYamlScalar(value) {
    const trimmed = String(value || "").trim();
    if (!trimmed) return "";
    if (
      (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
      (trimmed.startsWith("'") && trimmed.endsWith("'"))
    ) {
      return trimmed.slice(1, -1);
    }
    return trimmed.split(/\s+#/)[0].trim();
  }

  module.exports = {
    getTripScenes,
    getLifeAlbumScenes,
    generateSceneImage,
    generateLifeAlbumImage,
  };
})();
