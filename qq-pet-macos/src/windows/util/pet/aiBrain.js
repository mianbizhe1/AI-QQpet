/**
 * AI企鹅大脑核心
 * 负责：感知输入 → 决策 → 对话生成 → 动作执行
 */

(() => {
    'use strict';

    const http = require('http');
    const path = require('path');
    const { spawn } = require('child_process');
    const { captureScreen: captureDesktopScreen } = require('../screenshot');

    // ==================== 配置 ====================
    const AI_CONFIG = {
        // 主动触达冷却时间（毫秒）
        INITIATIVE_COOLDOWN: {
            'emotional_care': 4 * 60 * 60 * 1000,      // 情感关怀：4小时
            'social_bridge': 2 * 60 * 60 * 1000,       // 社交搭桥：2小时
            'pet_need': 30 * 60 * 1000,                // 宠物需求：30分钟
            'idle_chat': 60 * 60 * 1000,               // 闲聊：1小时
        },
        // 活跃时间段（小时）
        ACTIVE_HOURS: { start: 8, end: 23 },
        // 深夜模式（不主动打扰）
        QUIET_HOURS: { start: 0, end: 7 },
        // 感知检查间隔
        PERCEPTION_INTERVAL: 30 * 1000,  // 30秒检查一次
        AGENT_HOST: '127.0.0.1',
        AGENT_PORT: 18080,
        AGENT_STARTUP_WAIT: 800,
        AGENT_REQUEST_TIMEOUT: 60000,
        AGENT_TICK_MIN_INTERVAL: 2 * 60 * 1000,
        AGENT_TICK_URGENT_INTERVAL: 30 * 1000,
        PERIODIC_SCREENSHOT_INTERVAL: 30 * 60 * 1000,
        VISION_STATUS_CACHE_TTL: 5 * 60 * 1000,
        STARTUP_WEATHER_DELAY: 5000,
    };

    // ==================== 感知引擎 ====================
    class AIPerception {
        constructor(brain) {
            this.brain = brain;
            this.lastScreenCapture = 0;
            this.screenCaptureInterval = 60000; // 屏幕截取间隔
        }

        /**
         * 截取用户屏幕（通过 Electron IPC）
         */
        async captureScreen() {
            try {
                if (captureDesktopScreen) {
                    const result = await captureDesktopScreen();
                    if (result && result.success && result.filepath) {
                        console.log('[AIPerception] Screenshot captured through bash screencapture');
                        return {
                            filepath: result.filepath,
                            sizeKb: result.sizeKb || 0,
                        };
                    }
                    console.warn('[AIPerception] Screenshot failed:', result && result.error);
                }
                console.warn('[AIPerception] Screenshot not available');
                return null;
            } catch (error) {
                console.error('[AIPerception] Screenshot failed:', error);
                return null;
            }
        }

        /**
         * 检查消息是否需要截图
         */
        needsScreenshot(message) {
            if (!message) return false;
            const keywords = ['看看', '截屏', '屏幕', '在做', '什么', '忙', '工作'];
            return keywords.some(k => message.includes(k));
        }

        /**
         * 获取当前时间感知
         */
        getTimeContext() {
            const now = new Date();
            const hour = now.getHours();
            
            let period = 'unknown';
            if (hour >= 8 && hour <= 12) period = 'morning';
            else if (hour > 12 && hour <= 14) period = 'lunch';
            else if (hour > 14 && hour <= 18) period = 'afternoon';
            else if (hour > 18 && hour <= 22) period = 'evening';
            else if (hour > 22 || hour <= 0) period = 'late_night';
            else if (hour > 0 && hour < 8) period = 'midnight';

            const isQuietHour = hour >= AI_CONFIG.QUIET_HOURS.start && hour < AI_CONFIG.QUIET_HOURS.end;
            
            return {
                hour,
                period,
                isQuietHour,
                dayOfWeek: now.getDay(),
                isWeekend: now.getDay() === 0 || now.getDay() === 6
            };
        }

        /**
         * 分析宠物状态
         */
        analyzePetState(petInfo) {
            if (!petInfo || !petInfo.info) {
                return { needs: [], urgency: 0, overallMood: 'happy', hunger: 0, clean: 0, mood: 0, health: 5 };
            }
            const needs = [];

            if (petInfo.info.health === 0) {
                needs.push({ type: 'dead', urgency: 10, msg: '主人，我好像...不行了...' });
            } else if (petInfo.activeOption?.ill) {
                needs.push({ type: 'sick', urgency: 8, msg: `我好像生病了...${petInfo.activeOption.ill.name}` });
            }
            
            if (petInfo.info.hunger < 720) {
                const level = petInfo.info.hunger < 200 ? 'critical' : 'hungry';
                needs.push({ type: 'hungry', urgency: level === 'critical' ? 7 : 5, msg: '肚子在叫了...' });
            }
            
            if (petInfo.info.clean < 1080) {
                const level = petInfo.info.clean < 300 ? 'critical' : 'dirty';
                needs.push({ type: 'dirty', urgency: level === 'critical' ? 6 : 4, msg: '身上有点痒...' });
            }
            
            if (petInfo.info.mood < 100) {
                needs.push({ type: 'sad', urgency: 3, msg: '心情不太好...' });
            }

            // 综合心情评估
            let overallMood = 'happy';
            if (petInfo.info.mood < 200) overallMood = 'sad';
            else if (petInfo.info.mood < 500) overallMood = 'bored';
            else if (petInfo.info.mood < 800) overallMood = 'normal';

            return {
                needs,
                urgency: needs.length > 0 ? Math.max(...needs.map(n => n.urgency)) : 0,
                overallMood,
                hunger: petInfo.info.hunger,
                clean: petInfo.info.clean,
                mood: petInfo.info.mood,
                health: petInfo.info.health
            };
        }

        /**
         * 分析用户交互上下文
         */
        analyzeUserContext() {
            // 从全局获取用户活动状态
            const userActivity = global.userActivity || {
                isActive: true,
                lastActiveTime: Date.now(),
                idleMinutes: 0
            };

            let activityLevel = 'active';
            if (userActivity.isIdle || userActivity.idleMinutes > 5) {
                activityLevel = 'idle';
            } else if (!userActivity.isActive) {
                activityLevel = 'away';
            }

            return {
                activityLevel,
                lastActiveTime: userActivity.lastActiveTime,
                idleMinutes: userActivity.idleMinutes || 0,
                canInteract: activityLevel === 'idle' || activityLevel === 'active'
            };
        }
    }

    // ==================== 记忆系统 ====================
    class AIMemory {
        constructor(brain) {
            this.brain = brain;
            this.shortTerm = [];  // 短期记忆：当前会话
            this.midTerm = [];    // 中期记忆：重要事件（已修复：之前是死代码）
            this.personality = this.loadPersonality();
            this.lastInteraction = {};
            this.cooldowns = {};
            this._loadFromStore(); // 从 electron-store 恢复记忆
        }

        /**
         * 从 electron-store 加载记忆（持久化支持）
         */
        _loadFromStore() {
            try {
                if (global.$Store) {
                    const stored = global.$Store.getItem('aiMemory');
                    if (stored) {
                        this.shortTerm = stored.shortTerm || [];
                        this.midTerm = stored.midTerm || [];
                        // 清理过期记忆（超过7天的中期记忆）
                        const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
                        this.midTerm = this.midTerm.filter(m => m.timestamp > weekAgo);
                    }
                }
            } catch (e) {
                console.warn('[AIMemory] _loadFromStore failed:', e);
            }
        }

        /**
         * 保存记忆到 electron-store（持久化支持）
         */
        _saveToStore() {
            try {
                if (global.$Store) {
                    global.$Store.setItem('aiMemory', {
                        shortTerm: this.shortTerm,
                        midTerm: this.midTerm,
                    });
                }
            } catch (e) {
                console.warn('[AIMemory] _saveToStore failed:', e);
            }
        }

        /**
         * 刷新性格配置（从游戏状态重新派生）
         * 修复：之前 updatePersonality 是空操作，现在会真正刷新
         */
        refreshPersonality() {
            const oldPersonality = this.personality;
            this.personality = this.loadPersonality();
            if (JSON.stringify(oldPersonality) !== JSON.stringify(this.personality)) {
                console.log('[AIMemory] Personality updated:', this.personality);
            }
        }

        /**
         * 加载性格配置（从 electron-store 派生）
         */
        loadPersonality() {
            try {
                // 从 electron-store 读取派生个性
                const petInfo = (typeof getPetInfo === 'function') ? getPetInfo() : null;
                const info = petInfo?.info || {};
                if (info.aiWarmth !== undefined) {
                    return {
                        warmth: info.aiWarmth,
                        humor: info.aiHumor,
                        boldness: info.aiBoldness,
                        curiosity: info.aiCuriosity,
                        familiarity: info.aiFamiliarity,
                    };
                }
                // 旧数据：使用派生规则
                return {
                    warmth: 0.3 + (info.interactionCount || 0) * 0.002 + (info.charm || 0) * 0.001,
                    humor: 0.5,
                    boldness: 0.2 + (info.intel || 0) * 0.002,
                    curiosity: 0.7,
                    familiarity: Math.min(1, (info.interactionCount || 0) / 500),
                };
            } catch (e) {
                console.warn('[AIMemory] loadPersonality failed, using defaults:', e);
                return {
                    warmth: 0.5, humor: 0.5, boldness: 0.5, curiosity: 0.7, familiarity: 0.3,
                };
            }
        }

        /**
         * 保存性格（通过 electron-store 记录互动）
         */
        savePersonality() {
            // 个性由 recordInteraction 派生并持久化到 electron-store
            if (global.recordInteraction) {
                global.recordInteraction();
            }
        }

        /**
         * 更新性格（基于互动，触发重新派生）
         * 修复：现在会真正刷新 personality 并持久化
         */
        updatePersonality(eventType, delta) {
            // 刷新 personality（从游戏状态重新派生）
            this.refreshPersonality();
            // 触发 electron-store 持久化
            this.savePersonality();
        }

        /**
         * 添加短期记忆
         */
        addShortTerm(event) {
            this.shortTerm.push({
                ...event,
                timestamp: Date.now()
            });
            // 只保留最近20条
            if (this.shortTerm.length > 20) {
                this.shortTerm.shift();
            }
            this._saveToStore(); // 持久化
        }

        /**
         * 添加中期记忆
         * 修复：之前 midTerm 写了但从未被读取
         */
        addMidTerm(event) {
            // 判断是否值得记住（降低阈值从0.7到0.3）
            if (event.emotionIntensity >= 0.3 || this.isImportantEvent(event.type)) {
                this.midTerm.push({
                    ...event,
                    timestamp: Date.now(),
                    importance: event.emotionIntensity || this._calcImportance(event)
                });
                // 只保留最近100条
                if (this.midTerm.length > 100) {
                    // 按重要性排序，删除最不重要的
                    this.midTerm.sort((a, b) => (b.importance || 0.5) - (a.importance || 0.5));
                    this.midTerm.pop();
                }
                // 触发性格更新
                this.updatePersonality(event.type, event.emotionIntensity * 0.01);
                this._saveToStore(); // 持久化
            }
        }

        /**
         * 计算事件重要性
         */
        _calcImportance(event) {
            let importance = 0.5;
            // 重要事件类型加权
            const importantTypes = ['exam', 'love', 'work_change', 'birthday', 'pet_milestone',
                                   'health', 'achievement', 'milestone', 'holiday'];
            if (importantTypes.includes(event.type)) {
                importance += 0.3;
            }
            // 有内容的权重重叠
            if (event.content && event.content.length > 20) {
                importance += 0.1;
            }
            return Math.min(1.0, importance);
        }

        /**
         * 判断是否重要事件（扩大范围）
         */
        isImportantEvent(type) {
            return ['exam', 'love', 'work_change', 'birthday', 'pet_milestone',
                    'health', 'achievement', 'milestone', 'holiday', 'game'].includes(type);
        }

        /**
         * 获取最近的互动（包含 shortTerm + midTerm）
         * 修复：之前只返回 shortTerm，midTerm 是死代码
         */
        getRecentInteractions(limit = 5) {
            // 合并 shortTerm 和 midTerm，按时间排序
            const all = [...this.midTerm, ...this.shortTerm];
            // 应用时间衰减：越久远权重越低
            const now = Date.now();
            const scored = all.map(item => ({
                ...item,
                _score: (item.importance || 0.5) * this._timeDecay(now - item.timestamp)
            }));
            // 按分数和时间排序
            scored.sort((a, b) => {
                if (b._score !== a._score) return b._score - a._score;
                return b.timestamp - a.timestamp;
            });
            return scored.slice(0, limit);
        }

        /**
         * 时间衰减函数（越久远权重越低）
         */
        _timeDecay(ageMs) {
            const hour = ageMs / (1000 * 60 * 60);
            const day = hour / 24;
            // 7天后衰减到50%
            return Math.pow(0.5, day / 7);
        }

        /**
         * 获取中期记忆（供外部使用）
         */
        getMidTerm(limit = 20) {
            const now = Date.now();
            return this.midTerm
                .filter(m => this._timeDecay(now - m.timestamp) > 0.3)
                .slice(-limit);
        }

        /**
         * 检查冷却状态
         */
        isOnCooldown(actionType) {
            const lastTime = this.cooldowns[actionType] || 0;
            const cooldown = AI_CONFIG.INITIATIVE_COOLDOWN[actionType] || 3600000;
            return Date.now() - lastTime < cooldown;
        }

        /**
         * 设置冷却
         */
        setCooldown(actionType) {
            this.cooldowns[actionType] = Date.now();
        }

        /**
         * 获取记忆上下文（用于生成对话）
         * 修复：现在真正使用 midTerm
         */
        getContextForDialogue() {
            const recent = this.getRecentInteractions(5);
            const midTermTopics = this.getMidTerm(3);
            const context = {
                personality: this.personality,
                recentTopics: recent.map(r => r.content).filter(Boolean),
                midTermTopics: midTermTopics.map(m => m.content).filter(Boolean),
                lastInteractionTime: recent.length > 0 ? recent[recent.length - 1].timestamp : null,
            };
            return context;
        }

        /**
         * 与后端记忆系统同步
         */
        async syncWithBackend() {
            if (!this.brain) return;
            try {
                // 获取后端推荐
                const result = await this.brain.httpJson('GET', '/memory/recommend?num=3');
                if (result && result.recommendations) {
                    // 将后端推荐合并到 midTerm
                    for (const rec of result.recommendations) {
                        if (rec.type === 'entertainment' || rec.type === 'hot_topic') {
                            this.addMidTerm({
                                type: 'backend_recommend',
                                content: rec.content,
                                emotionIntensity: 0.4,
                                source: 'backend'
                            });
                        }
                    }
                }
            } catch (e) {
                console.warn('[AIMemory] syncWithBackend failed:', e);
            }
        }
    }

    // ==================== 对话生成器 ====================
    class AIDialogue {
        constructor(brain) {
            this.brain = brain;
            this.templateCache = new Map();
        }

        /**
         * 生成对话
         */
        generate(context) {
            const { type, petState, userContext, memory } = context;
            const personality = memory.personality;

            // 根据类型选择生成策略
            switch(type) {
                case 'pet_need':
                    return this.generatePetNeedDialogue(petState, personality);
                case 'emotional_care':
                    return this.generateEmotionalCareDialogue(userContext, personality);
                case 'social_bridge':
                    return this.generateSocialBridgeDialogue(userContext, personality);
                case 'idle':
                    return this.generateIdleDialogue(memory, personality);
                case 'click_response':
                    return this.generateClickResponseDialogue(petState, personality);
                default:
                    return this.generateDefaultDialogue(personality);
            }
        }

        /**
         * 生成宠物需求对话
         */
        generatePetNeedDialogue(petState, personality) {
            const templates = {
                hungry: [
                    '肚子咕噜咕噜叫了...',
                    '主人，我好像闻到食物的香味了~',
                    '好饿呀，能给我点吃的吗？',
                    '（眼巴巴地看着你）',
                ],
                dirty: [
                    '身上有点痒痒的...',
                    '好久没洗澡了...',
                    '（扭来扭去）',
                ],
                sick: [
                    '咳咳...有点不舒服',
                    '头有点晕...',
                    '（趴在原地不动）',
                ],
                dead: [
                    '主人...谢谢你一直照顾我...',
                    '我可能要先睡一会儿了...',
                ]
            };

            const type = petState.needs[0]?.type || 'hungry';
            const pool = templates[type] || templates.hungry;
            const base = pool[Math.floor(Math.random() * pool.length)];

            // 根据性格调整语气
            let suffix = '';
            if (personality.warmth > 0.7) {
                suffix = '主人~';
            } else if (personality.humor > 0.7) {
                suffix = '嘿嘿';
            }

            return suffix ? `${suffix}，${base.replace('主人', '')}` : base;
        }

        /**
         * 生成情感关怀对话
         */
        generateEmotionalCareDialogue(userContext, personality) {
            if (personality.warmth > 0.7) {
                return '看你好像有点累，要不要休息一下？';
            } else if (personality.humor > 0.7) {
                return '（默默递上一杯水）';
            } else {
                return '（安静地陪在你身边）';
            }
        }

        /**
         * 生成社交搭桥对话
         */
        generateSocialBridgeDialogue(userContext, personality) {
            const messages = [
                '小明的企鹅说它主人最近都没怎么陪它玩...',
                '你有个好久没联系的朋友，要不要去看看？',
                '（带来好友的问候）',
            ];
            return messages[Math.floor(Math.random() * messages.length)];
        }

        /**
         * 生成闲置闲聊
         */
        generateIdleDialogue(memory, personality) {
            const recentTopics = memory.shortTerm.map(s => s.content).filter(Boolean);
            
            if (recentTopics.length > 0 && Math.random() > 0.5) {
                return `上次你说到...${recentTopics[recentTopics.length - 1]}`;
            }

            const idleTemplates = [
                '（发呆中）',
                '今天天气不错呢~',
                '主人最近在忙什么呀？',
                '（轻轻摇摆）',
                '好无聊呀...',
            ];
            
            return idleTemplates[Math.floor(Math.random() * idleTemplates.length)];
        }

        /**
         * 生成点击响应
         */
        generateClickResponseDialogue(petState, personality) {
            const reactions = [
                '好开心！',
                '主人最好了~',
                '（撒娇地蹭了蹭）',
                '再摸摸我嘛~',
                '嘿嘿~',
                '（满足地眯眼）',
                '好暖和呀！',
            ];

            const reaction = reactions[Math.floor(Math.random() * reactions.length)];
            
            // 心情好时的特殊反应
            if (petState.overallMood === 'happy' && personality.humor > 0.6) {
                return `${reaction} 来陪我玩嘛~`;
            }
            
            return reaction;
        }

        /**
         * 生成默认对话
         */
        generateDefaultDialogue(personality) {
            const defaults = [
                '在吗？',
                '今天怎么样？',
                '（企鹅歪头）',
            ];
            return defaults[Math.floor(Math.random() * defaults.length)];
        }
    }

    // ==================== AI大脑核心 ====================
    class AIBrain {
        constructor() {
            this.perception = new AIPerception(this);
            this.memory = new AIMemory(this);
            this.dialogue = new AIDialogue(this);
            this.isRunning = false;
            this.tickInterval = null;
            this.lastDecision = null;
            this.serverProcess = null;
            this.serverStarting = null;
            this.lastAgentTickAt = 0;
            this.lastPeriodicScreenshotAt = 0;
            this.visionStatusCache = null;
            this.visionStatusCheckedAt = 0;
            this.tickCount = 0;
            this.MEMORY_SYNC_INTERVAL = 20; // 每20个tick（约10分钟）同步一次后端记忆
        }

        updateUserActivity(patch = {}) {
            const previous = global.userActivity || {
                isActive: true,
                isIdle: false,
                lastActiveTime: Date.now(),
                idleMinutes: 0,
            };

            global.userActivity = {
                ...previous,
                ...patch,
            };
        }

        /**
         * 启动AI大脑
         */
        async start() {
            if (this.isRunning) return;
            await this.ensureAgentServer();
            this.isRunning = true;
            this.updateUserActivity();
            
            // 启动主循环
            this.tickInterval = setInterval(() => {
                this.tick().catch((error) => {
                    console.error('[AIBrain] Tick loop error:', error);
                });
            }, AI_CONFIG.PERCEPTION_INTERVAL);

            setTimeout(() => {
                this.announceStartupWeather().catch((error) => {
                    console.error('[AIBrain] announceStartupWeather failed:', error);
                });
            }, AI_CONFIG.STARTUP_WEATHER_DELAY);

            console.log('[AIBrain] AI企鹅大脑已启动');
        }

        async announceStartupWeather() {
            if (!this.isRunning) return;

            try {
                const result = await this.httpJson('POST', '/weather/briefing', {
                    auto_locate: true,
                    reasoning: '应用启动时自动获取当前位置天气和未来预报，提醒主人',
                });

                if (!result?.success) {
                    console.warn('[AIBrain] Startup weather unavailable:', result?.error);
                    return;
                }

                const dialogue = String(result.reminder || result.content || '').trim();
                if (!dialogue || !global.openSpeak) return;

                global.openSpeak({
                    data: {
                        type: 'text',
                        data: dialogue,
                        submitText: '',
                        mustSpeak: true,
                    },
                    active: 'speak',
                });

                this.memory.addShortTerm({
                    type: 'startup_weather',
                    content: dialogue,
                    triggered: true,
                });
            } catch (error) {
                console.error('[AIBrain] announceStartupWeather error:', error);
            }
        }

        /**
         * 停止AI大脑
         */
        stop() {
            if (this.tickInterval) {
                clearInterval(this.tickInterval);
                this.tickInterval = null;
            }
            this.isRunning = false;
            console.log('[AIBrain] AI企鹅大脑已停止');
        }

        /**
         * 主循环
         */
        async tick() {
            if (!this.isRunning) return;

            this.tickCount++;

            try {
                const lastActiveTime = global.userActivity?.lastActiveTime || Date.now();
                const idleMinutes = Math.max(0, Math.floor((Date.now() - lastActiveTime) / 60000));
                this.updateUserActivity({
                    idleMinutes,
                    isIdle: idleMinutes >= 5,
                    isActive: idleMinutes < 30,
                });

                const petInfo = getPetInfo();
                const petState = this.perception.analyzePetState(petInfo);
                const timeContext = this.perception.getTimeContext();
                const userContext = this.perception.analyzeUserContext();

                await this.maybeCapturePeriodicScreenshot();

                const fallbackDecision = this.decide(petState, timeContext, userContext);
                if (this.shouldRequestAgentForTick(petState, fallbackDecision)) {
                    const decision = await this.requestAgentDecision('tick', {
                        petState,
                        timeContext,
                        userContext,
                    });

                    if (decision?.decision) {
                        this.lastAgentTickAt = Date.now();
                        this.applyAgentDecision(decision.decision, 'tick');
                    }

                    // 检查是否有待显示的定时任务通知
                    if (decision?.pending_notifications && decision.pending_notifications.length > 0) {
                        console.log('[AIBrain] 有待显示的通知:', decision.pending_notifications);
                        for (const notification of decision.pending_notifications) {
                            await this.displayNotification(notification);
                        }
                    }

                    if (decision?.decision) {
                        return;
                    }
                }

                if (fallbackDecision.shouldAct) {
                    this.execute(fallbackDecision);
                }

                // 定期从后端同步记忆（约每10分钟一次）
                if (this.tickCount % this.MEMORY_SYNC_INTERVAL === 0) {
                    this._syncMemoryFromBackend().catch((e) => {
                        console.warn('[AIBrain] _syncMemoryFromBackend error:', e);
                    });
                }
            } catch (error) {
                console.error('[AIBrain] Tick error:', error);
            }
        }

        /**
         * 显示定时任务通知
         */
        async displayNotification(notification) {
            const { task_name, result, skill_name } = notification;

            // 格式化通知内容
            let dialogue = '';
            if (skill_name === 'skillhub_search') {
                dialogue = `主人~我刚帮你找了一些好用的技能！\n\n${result}\n\n喜欢吗~`;
            } else {
                dialogue = `主人~有一个新消息：\n\n${result}`;
            }

            // 通过 openSpeak 显示
            if (global.openSpeak) {
                global.openSpeak({
                    data: {
                        type: 'text',
                        data: dialogue,
                        submitText: '',
                    },
                    active: 'speak',
                });
            }

            // 记录到记忆
            this.memory.addShortTerm({
                type: 'notification',
                taskName: task_name,
                skillName: skill_name,
                content: dialogue,
            });
        }

        async ensureAgentServer() {
            if (this.serverStarting) {
                return this.serverStarting;
            }

            this.serverStarting = (async () => {
                const healthy = await this.checkAgentHealth();
                if (healthy) {
                    return true;
                }

                if (!this.serverProcess || this.serverProcess.exitCode !== null) {
                    this.startAgentServerProcess();
                }

                for (let i = 0; i < 15; i += 1) {
                    await this.sleep(AI_CONFIG.AGENT_STARTUP_WAIT);
                    if (await this.checkAgentHealth()) {
                        return true;
                    }
                }

                throw new Error('Python AI agent server failed to start');
            })();

            try {
                return await this.serverStarting;
            } finally {
                this.serverStarting = null;
            }
        }

        startAgentServerProcess() {
            const serverScript = path.resolve(__dirname, '../../../../../src/ai_server.py');
            this.serverProcess = spawn('python3', [serverScript], {
                stdio: ['ignore', 'pipe', 'pipe'],
            });

            this.serverProcess.stdout?.on('data', (chunk) => {
                const text = String(chunk).trim();
                if (text) console.log(`[AIAgentServer] ${text}`);
            });

            this.serverProcess.stderr?.on('data', (chunk) => {
                const text = String(chunk).trim();
                if (text) console.error(`[AIAgentServer] ${text}`);
            });

            this.serverProcess.on('exit', (code) => {
                console.log(`[AIAgentServer] exited with code ${code}`);
            });
        }

        async checkAgentHealth() {
            try {
                const response = await this.httpJson('GET', '/health');
                return response?.status === 'ok';
            } catch (_) {
                return false;
            }
        }

        async getVisionStatus() {
            const now = Date.now();
            if (this.visionStatusCache && now - this.visionStatusCheckedAt < AI_CONFIG.VISION_STATUS_CACHE_TTL) {
                return this.visionStatusCache;
            }

            try {
                await this.ensureAgentServer();
                const status = await this.httpJson('GET', '/ai/vision/status');
                this.visionStatusCache = status || { enabled: false };
                this.visionStatusCheckedAt = now;
                return this.visionStatusCache;
            } catch (error) {
                console.error('[AIBrain] getVisionStatus error:', error);
                this.visionStatusCache = { enabled: false };
                this.visionStatusCheckedAt = now;
                return this.visionStatusCache;
            }
        }

        async maybeCapturePeriodicScreenshot() {
            const now = Date.now();
            if (now - this.lastPeriodicScreenshotAt < AI_CONFIG.PERIODIC_SCREENSHOT_INTERVAL) {
                return;
            }

            const visionStatus = await this.getVisionStatus();
            if (!visionStatus?.enabled) {
                return;
            }

            this.lastPeriodicScreenshotAt = now;
            console.log('[AIBrain] Periodic screenshot triggered for vision context');

            const screenshotData = await this.perception.captureScreen();
            if (!screenshotData) {
                return;
            }

            const response = await this.requestAgentDecision('vision_watch', {
                userMessage: '这是定时后台观察。请基于截图生成一句简短视觉上下文，描述主人可能正在做什么；不要要求主人回应。',
                screenshotData,
            });

            if (response?.decision) {
                this.applyAgentDecision(response.decision, 'vision_watch');
                return;
            }

            this.memory.addShortTerm({
                type: 'vision_watch',
                content: '[vision screenshot captured]',
                action: 'none',
                triggered: false,
            });
        }

        async requestAgentDecision(event, extraContext = {}) {
            try {
                await this.ensureAgentServer();

                const payload = {
                    event,
                    execute: true,
                    message: extraContext.userMessage || '',
                    user_context: {
                        ...this.perception.analyzeUserContext(),
                        ...extraContext.userContext,
                        screenshotData: extraContext.screenshotData || null,
                    },
                    recent_memory: this.memory.getRecentInteractions(8).map((item) => ({
                        type: item.type,
                        content: item.content,
                        timestamp: item.timestamp,
                    })),
                    local_context: {
                        petState: extraContext.petState || null,
                        timeContext: extraContext.timeContext || null,
                    },
                };

                return await this.httpJson('POST', '/ai/decide', payload);
            } catch (error) {
                console.error('[AIBrain] requestAgentDecision error:', error);
                return null;
            }
        }

        shouldRequestAgentForTick(petState, fallbackDecision) {
            if (!fallbackDecision?.shouldAct) {
                return false;
            }

            const now = Date.now();
            const interval = petState.urgency >= 8
                ? AI_CONFIG.AGENT_TICK_URGENT_INTERVAL
                : AI_CONFIG.AGENT_TICK_MIN_INTERVAL;

            if (petState.urgency < 5) {
                return false;
            }

            return now - this.lastAgentTickAt >= interval;
        }

        applyAgentDecision(decision, sourceEvent = 'tick') {
            if (!decision) return;

            const dialogue = String(decision.dialogue || '').trim();
            const action = decision.action || 'none';
            const actionResult = decision.action_result || null;

            if (dialogue && global.openSpeak) {
                global.openSpeak({
                    data: {
                        type: 'text',
                        data: dialogue,
                        submitText: '',
                    },
                    active: 'speak',
                });
            }

            this.memory.addShortTerm({
                type: sourceEvent,
                content: dialogue || `[action:${action}]`,
                action,
                actionResult,
                triggered: true,
            });

            this.lastDecision = decision;
        }

        async chatWithAgent(message) {
            this.updateUserActivity({
                isActive: true,
                isIdle: false,
                idleMinutes: 0,
                lastActiveTime: Date.now(),
            });

            // 如果消息可能需要截图，先截取
            let screenshotData = null;
            if (this.perception.needsScreenshot(message)) {
                console.log('[AIBrain] Message may need screenshot, capturing...');
                screenshotData = await this.perception.captureScreen();
            }

            // 构建发送给 Agent 的上下文
            const agentContext = {
                userMessage: message,
                screenshotData,  // 如果有截图会包含文件路径和大小
            };

            const response = await this.requestAgentDecision('chat', agentContext);

            if (response?.decision) {
                this.applyAgentDecision(response.decision, 'chat');

                // 发送对话到后端进行学习（异步，不阻塞响应）
                this._learnFromConversation(message, response.decision.dialogue);

                return response.decision;
            }

            return {
                action: 'none',
                dialogue: '我刚刚有点走神，再和我说一次吧~',
                reason: 'agent unavailable',
                priority: 0,
            };
        }

        /**
         * 发送对话到后端进行学习
         */
        async _learnFromConversation(userMessage, petResponse) {
            if (!userMessage) return;
            try {
                await this.httpJson('POST', '/memory/learn', {
                    messages: [
                        { role: 'user', content: userMessage },
                        { role: 'assistant', content: petResponse || '' }
                    ],
                    pet_name: '小Q',
                });
            } catch (e) {
                console.warn('[AIBrain] _learnFromConversation failed:', e);
            }
        }

        /**
         * 从后端同步记忆（定期调用）
         */
        async _syncMemoryFromBackend() {
            try {
                // 获取后端推荐
                const result = await this.httpJson('GET', '/memory/recommend?num=3');
                if (result && result.recommendations) {
                    for (const rec of result.recommendations) {
                        if (rec.type === 'entertainment' || rec.type === 'hot_topic') {
                            this.memory.addMidTerm({
                                type: 'backend_recommend',
                                content: rec.content,
                                emotionIntensity: 0.4,
                                source: 'backend'
                            });
                        }
                    }
                }

                // 获取主人画像用于更新上下文
                const profile = await this.httpJson('GET', '/memory/master');
                if (profile && profile.interests) {
                    // 将兴趣注入到 midTerm 供对话生成使用
                    for (const interest of profile.interests.slice(0, 3)) {
                        this.memory.addMidTerm({
                            type: 'interest',
                            content: `主人对${interest}感兴趣`,
                            emotionIntensity: 0.3,
                            source: 'profile'
                        });
                    }
                }
            } catch (e) {
                console.warn('[AIBrain] _syncMemoryFromBackend failed:', e);
            }
        }

        httpJson(method, requestPath, payload) {
            return new Promise((resolve, reject) => {
                const body = payload ? JSON.stringify(payload) : null;
                const req = http.request({
                    hostname: AI_CONFIG.AGENT_HOST,
                    port: AI_CONFIG.AGENT_PORT,
                    path: requestPath,
                    method,
                    timeout: AI_CONFIG.AGENT_REQUEST_TIMEOUT,
                    headers: body ? {
                        'Content-Type': 'application/json',
                        'Content-Length': Buffer.byteLength(body),
                    } : undefined,
                }, (res) => {
                    let raw = '';
                    res.setEncoding('utf8');
                    res.on('data', (chunk) => {
                        raw += chunk;
                    });
                    res.on('end', () => {
                        try {
                            const parsed = raw ? JSON.parse(raw) : {};
                            if (res.statusCode >= 400) {
                                reject(new Error(parsed.error || parsed.message || `HTTP ${res.statusCode}`));
                                return;
                            }
                            resolve(parsed);
                        } catch (error) {
                            reject(error);
                        }
                    });
                });

                req.on('error', reject);
                req.on('timeout', () => {
                    req.destroy(new Error(`Request timeout: ${method} ${requestPath}`));
                });

                if (body) {
                    req.write(body);
                }
                req.end();
            });
        }

        sleep(ms) {
            return new Promise((resolve) => setTimeout(resolve, ms));
        }

        /**
         * 决策逻辑
         */
        decide(petState, timeContext, userContext) {
            // 深夜模式：只处理紧急宠物需求
            if (timeContext.isQuietHour) {
                if (petState.urgency >= 8) {
                    return { shouldAct: true, type: 'pet_need', priority: petState.urgency };
                }
                return { shouldAct: false };
            }

            // 检查宠物需求（高优先级）
            if (petState.urgency >= 5) {
                if (!this.memory.isOnCooldown('pet_need')) {
                    this.memory.setCooldown('pet_need');
                    return { shouldAct: true, type: 'pet_need', priority: petState.urgency };
                }
            }

            // 检查用户情绪（需要更复杂的感知，这里先预留接口）
            if (userContext.activityLevel === 'idle' && !this.memory.isOnCooldown('idle_chat')) {
                // 只有心情好的时候才闲聊
                if (petState.overallMood === 'happy' && Math.random() > 0.7) {
                    this.memory.setCooldown('idle_chat');
                    return { shouldAct: true, type: 'idle', priority: 2 };
                }
            }

            return { shouldAct: false };
        }

        /**
         * 执行决策
         */
        execute(decision) {
            const petInfo = getPetInfo();
            const petState = this.perception.analyzePetState(petInfo);
            const userContext = this.perception.analyzeUserContext();

            const actionResult = this.performAction(decision, petState);
            const actionLabel = actionResult?.message || actionResult?.success === false
                ? actionResult.message
                : null;

            // 生成对话
            const dialogue = this.dialogue.generate({
                type: decision.type,
                petState,
                userContext,
                memory: this.memory
            });

            // 触发显示（通过全局openSpeak）
            if (global.openSpeak) {
                global.openSpeak({
                    data: {
                        type: 'text',
                        data: actionLabel ? `${actionLabel}\n${dialogue}` : dialogue,
                        submitText: '',
                    },
                    active: 'speak',
                    otherOpt: actionResult?.mood ? { mood: actionResult.mood } : null,
                });
            }

            // 记录这次主动行为
            this.memory.addShortTerm({
                type: decision.type,
                content: dialogue,
                triggered: true
            });

            this.lastDecision = decision;
        }

        performAction(decision, petState) {
            if (decision.type !== 'pet_need') {
                return { success: true };
            }

            const primaryNeed = petState.needs[0];
            if (!primaryNeed || !global.petControl?.Goods) {
                return { success: false, message: '' };
            }

            if (primaryNeed.type === 'hungry') {
                return this.autoUseConsumable('food', '我先自己找点吃的啦~', 10);
            }

            if (primaryNeed.type === 'dirty') {
                return this.autoUseConsumable('commodity', '我去冲个澡，马上香香的~', 8);
            }

            if (primaryNeed.type === 'sick' || primaryNeed.type === 'dead') {
                return this.autoUseMedicine(primaryNeed.type === 'dead');
            }

            return { success: true };
        }

        autoUseConsumable(type, message, mood = 0) {
            try {
                const goods = global.petControl?.Goods?.storeGoods?.[type] || [];
                if (!goods.length) {
                    return { success: false, message: type === 'food' ? '我饿了，可是库存里没有吃的了...' : '我想洗澡，可是仓库里没有清洁道具了...' };
                }

                const selected = this.pickBestConsumable(type, goods);
                if (!selected) {
                    return { success: false, message: '' };
                }

                const item = global.petControl.Goods.getGoodsInfo({ goodName: `${type}*${selected}` });
                const count = Number((selected.split('-')[1] || '1'));
                const payload = {
                    ...item,
                    type,
                    num: count,
                };

                const result = global.petControl.Goods.useConsumables(payload);
                if (result && !result.overType) {
                    return { success: true, message, mood };
                }

                return { success: false, message: result?.msg || '我试着自己处理了一下，但没成功...' };
            } catch (error) {
                console.error('[AIBrain] autoUseConsumable error:', error);
                return { success: false, message: '我刚刚想自己处理一下，结果出了一点小状况...' };
            }
        }

        pickBestConsumable(type, goods) {
            let best = null;
            let bestScore = -Infinity;

            for (const entry of goods) {
                const item = global.petControl.Goods.getGoodsInfo({ goodName: `${type}*${entry}` });
                if (!item) continue;

                const score = Number(item.starve || item.clean || 0);
                if (score > bestScore) {
                    bestScore = score;
                    best = entry;
                }
            }

            return best || goods[0] || null;
        }

        autoUseMedicine(isRevive = false) {
            try {
                const illness = getPetInfoOne('', 'activeOption')?.ill;
                const cure = illness?.cure;
                if (!cure) {
                    return { success: false, message: isRevive ? '我好像需要复活道具...' : '我现在不太舒服，但还没找到合适的药...' };
                }

                const store = global.petControl?.Goods?.storeGoods?.medicine || [];
                const match = store.find((entry) => entry.startsWith(`${cure.name}-`) || entry.startsWith(`${cure.key}-`) || entry.startsWith(`${cure.icon}-`));
                if (!match) {
                    return { success: false, message: isRevive ? '我需要复活药水，可仓库里没有了...' : `我生病了，需要 ${cure.name}，但仓库里没有找到...` };
                }

                const item = global.petControl.Goods.getGoodsInfo({ goodName: `medicine*${match}` });
                const count = Number((match.split('-')[1] || '1'));
                const payload = {
                    ...item,
                    type: 'medicine',
                    num: count,
                };

                const result = global.petControl.Goods.useConsumables(payload);
                if (result && !result.overType) {
                    return {
                        success: true,
                        message: isRevive ? '我努力把自己救回来啦...' : '我已经乖乖吃药了，会快点好起来的~',
                        mood: 5,
                    };
                }

                return { success: false, message: result?.msg || '我想自己吃药，但刚刚没成功...' };
            } catch (error) {
                console.error('[AIBrain] autoUseMedicine error:', error);
                return { success: false, message: '我刚想自己吃药，结果卡了一下...' };
            }
        }

        /**
         * 处理用户点击
         */
        onPetClicked() {
            try {
                this.updateUserActivity({
                    isActive: true,
                    isIdle: false,
                    idleMinutes: 0,
                    lastActiveTime: Date.now(),
                });
                const petInfo = getPetInfo();
                const petState = this.perception.analyzePetState(petInfo);
                const dialogue = this.dialogue.generate({
                    type: 'click_response',
                    petState,
                    userContext: this.perception.analyzeUserContext(),
                    memory: this.memory,
                });

                const decision = {
                    action: 'none',
                    dialogue,
                    reason: 'local click response',
                    priority: 0,
                };

                this.applyAgentDecision(decision, 'click');
                return Promise.resolve(decision);
            } catch (error) {
                console.error('[AIBrain] onPetClicked error:', error);
                return Promise.resolve({
                    action: 'none',
                    dialogue: '（企鹅歪头）',
                    reason: 'click handler error',
                    priority: 0,
                });
            }
        }

        /**
         * 处理用户消息
         */
        onUserMessage(message) {
            this.updateUserActivity({
                isActive: true,
                isIdle: false,
                idleMinutes: 0,
                lastActiveTime: Date.now(),
            });
            this.memory.addShortTerm({
                type: 'user_message',
                content: message,
                timestamp: Date.now()
            });

            // 简单的响应逻辑
            const response = this.generateResponse(message);
            return response;
        }

        /**
         * 生成对用户消息的响应
         */
        generateResponse(message) {
            const context = this.memory.getContextForDialogue();
            const petInfo = getPetInfo();
            const petState = this.perception.analyzePetState(petInfo);

            // 关键词匹配
            const keywords = {
                greeting: ['你好', 'hi', 'hello', '在吗', '在不在'],
                feeding: ['吃', '饿', '喂', '食物'],
                cleaning: ['洗澡', '清洁', '脏'],
                playing: ['玩', '游戏', '无聊'],
                caring: ['乖', '可爱', '好棒', '棒'],
            };

            let category = 'unknown';
            for (const [key, words] of Object.entries(keywords)) {
                if (words.some(w => message.includes(w))) {
                    category = key;
                    break;
                }
            }

            const responses = {
                greeting: ['你好呀~', '主人！', '（开心地跳了一下）', '来啦来啦~'],
                feeding: ['想吃想吃！', '有什么好吃的呀？', '（眼睛发亮）'],
                cleaning: ['要洗澡澡~', '好呀好呀！', '（欢快地拍打翅膀）'],
                playing: ['玩什么玩什么！', '好呀好呀~', '（兴奋地转圈）'],
                caring: ['嘿嘿~', '谢谢主人夸奖！', '（得意地挺起胸脯）'],
                unknown: ['嗯嗯', '这样啊~', '（歪头）', '主人说什么呢？'],
            };

            const pool = responses[category] || responses.unknown;
            return pool[Math.floor(Math.random() * pool.length)];
        }

        /**
         * 获取当前状态
         */
        getStatus() {
            return {
                isRunning: this.isRunning,
                personality: this.memory.personality,
                shortTermCount: this.memory.shortTerm.length,
                midTermCount: this.memory.midTerm.length,
                cooldowns: this.memory.cooldowns,
            };
        }

        // ==================== 技能接口 ====================

        /**
         * 列出所有可用技能
         */
        async getAvailableSkills() {
            try {
                return await this.httpJson('GET', '/ai/skill/list');
            } catch (error) {
                console.error('[AIBrain] getAvailableSkills failed:', error);
                return { skills: [], error: error.message };
            }
        }

        /**
         * 执行技能
         * @param {string} skillName - 技能名称
         * @param {object} skillArgs - 技能参数
         * @param {object} options - 选项 { context: {}, async: false }
         */
        async executeSkill(skillName, skillArgs = {}, options = {}) {
            try {
                const payload = {
                    skill_name: skillName,
                    skill_args: skillArgs,
                    context: options.context || {},
                };
                const response = await this.httpJson('POST', '/ai/skill/execute', payload);

                // 记录到记忆
                this.memory.addShortTerm({
                    type: 'skill_execute',
                    skillName,
                    skillArgs,
                    result: response,
                });

                return response;
            } catch (error) {
                console.error('[AIBrain] executeSkill failed:', error);
                return { success: false, error: error.message };
            }
        }

        /**
         * 搜索技能
         * @param {string} query - 搜索关键词
         */
        async searchSkills(query) {
            try {
                const skills = await this.getAvailableSkills();
                const queryLower = query.toLowerCase();
                return skills.skills.filter(skill =>
                    skill.name.toLowerCase().includes(queryLower) ||
                    skill.description.toLowerCase().includes(queryLower) ||
                    (skill.aliases && skill.aliases.some(a => a.toLowerCase().includes(queryLower)))
                );
            } catch (error) {
                console.error('[AIBrain] searchSkills failed:', error);
                return [];
            }
        }

        // ==================== 定时任务接口 ====================

        /**
         * 添加定时任务
         * @param {object} taskConfig - 任务配置 { name, cron, skill_name, skill_args, context }
         */
        async scheduleTask(taskConfig) {
            try {
                const payload = {
                    name: taskConfig.name,
                    cron: taskConfig.cron,
                    skill_name: taskConfig.skill_name,
                    skill_args: taskConfig.skill_args || {},
                    context: taskConfig.context || {},
                };
                const response = await this.httpJson('POST', '/scheduler/task/add', payload);

                // 记录到记忆
                this.memory.addShortTerm({
                    type: 'schedule_task',
                    taskName: taskConfig.name,
                    cron: taskConfig.cron,
                    skillName: taskConfig.skill_name,
                });

                return response;
            } catch (error) {
                console.error('[AIBrain] scheduleTask failed:', error);
                return { success: false, error: error.message };
            }
        }

        /**
         * 列出所有定时任务
         */
        async getScheduledTasks() {
            try {
                return await this.httpJson('GET', '/scheduler/task/list');
            } catch (error) {
                console.error('[AIBrain] getScheduledTasks failed:', error);
                return { tasks: [], error: error.message };
            }
        }

        /**
         * 删除定时任务
         * @param {string} taskId - 任务ID
         */
        async removeScheduledTask(taskId) {
            try {
                return await this.httpJson('POST', '/scheduler/task/remove', { task_id: taskId });
            } catch (error) {
                console.error('[AIBrain] removeScheduledTask failed:', error);
                return { success: false, error: error.message };
            }
        }

        /**
         * 启用/禁用定时任务
         * @param {string} taskId - 任务ID
         * @param {boolean} enabled - 是否启用
         */
        async setScheduledTaskEnabled(taskId, enabled = true) {
            try {
                return await this.httpJson('POST', '/scheduler/task/enable', {
                    task_id: taskId,
                    enabled,
                });
            } catch (error) {
                console.error('[AIBrain] setScheduledTaskEnabled failed:', error);
                return { success: false, error: error.message };
            }
        }

        // ==================== Agent状态接口 ====================

        /**
         * 获取Agent和进程池状态
         */
        async getAgentStatus() {
            try {
                return await this.httpJson('GET', '/agent/status');
            } catch (error) {
                console.error('[AIBrain] getAgentStatus failed:', error);
                return { error: error.message };
            }
        }
    }

    // ==================== 导出 ====================
    // 挂载到全局
    global.AIBrain = AIBrain;
    global.aiBrainInstance = null;

    // 便捷方法
    global.initAIBrain = function() {
        if (!global.aiBrainInstance) {
            global.aiBrainInstance = new AIBrain();
        }
        return global.aiBrainInstance;
    };

    console.log('[AI] AI企鹅大脑模块已加载');

    try {
        module.exports = {
            AIBrain,
            initAIBrain: global.initAIBrain,
        };
    } catch (_) {}

})();
