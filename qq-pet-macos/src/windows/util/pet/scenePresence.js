(() => {
  const _require = eval("require");
  const https = _require("https");
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

  async function buildPrompt(option, petInfo) {
    const host = petInfo?.info?.host || "主人";
    let lifeContext = "";

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

    return [
      "A cute QQ Pet style penguin companion, black and white body, big round eyes, orange beak and feet, blue scarf, yellow star pendant.",
      option.memoir
        ? `Create a warm four-panel comic memoir about ${host}'s everyday life with this penguin companion.${lifeContext}`
        : `Create a photorealistic virtual travel photo of the penguin at ${option.scene || option.prompt}.`,
      "Keep the character recognizable, charming, friendly, full-body visible, cinematic composition, high quality, no text, no watermark.",
    ].join(" ");
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

  function getConfiguredApiKey() {
    return (
      readLlmApiKeyFromConfig() ||
      process.env.MINIMAX_API_KEY ||
      process.env.LLM_API_KEY ||
      ""
    );
  }

  function readLlmApiKeyFromConfig() {
    const configPaths = [
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
    generateSceneImage,
  };
})();
