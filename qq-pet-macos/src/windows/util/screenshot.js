/**
 * 截图工具 - 提供给 AI 企鹅使用
 * 通过 bash 执行 macOS screencapture 获取用户屏幕截图
 */

(() => {
    'use strict';

    const fs = require('fs');
    const path = require('path');
    const { spawn } = require('child_process');
    const { execFile } = require('child_process');
    const screenDir = path.resolve(__dirname, '../../../../screen');

    /**
     * 截取用户当前屏幕
     * @returns {Promise<{success: boolean, filepath?: string, sizeKb?: number, error?: string}>}
     */
    async function captureScreen() {
        const timestamp = `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
        fs.mkdirSync(screenDir, { recursive: true });
        const savePath = path.join(screenDir, `qqpet_screen_${timestamp}.png`);
        const command = `screencapture -x ${shellEscape(savePath)}`;
        const frontmost = await getFrontmostAppInfo();

        return new Promise((resolve) => {
            const child = spawn('bash', ['-lc', command], {
                stdio: ['ignore', 'pipe', 'pipe'],
            });

            let stderr = '';
            child.stderr.on('data', (chunk) => {
                stderr += String(chunk || '');
            });

            child.on('error', (error) => {
                console.error('[screenshot] bash spawn failed:', error);
                resolve({ success: false, error: String(error) });
            });

            child.on('close', () => {
                try {
                    if (!fs.existsSync(savePath)) {
                        resolve({
                            success: false,
                            error: normalizeCaptureError(stderr.trim() || '截图文件未生成'),
                        });
                        return;
                    }

                    const sizeKb = Math.round((fs.statSync(savePath).size / 1024) * 10) / 10;
                    resolve({
                        success: true,
                        filepath: savePath,
                        sizeKb,
                        frontmost_app: frontmost.appName,
                        frontmost_window: frontmost.windowTitle,
                    });
                } catch (error) {
                    console.error('[screenshot] capture failed:', error);
                    resolve({ success: false, error: String(error) });
                }
            });
        });
    }

    function shellEscape(filePath) {
        return `'${String(filePath).replace(/'/g, `'\\''`)}'`;
    }

    function getFrontmostAppInfo() {
        const script = `
            tell application "System Events"
                set frontProc to first application process whose frontmost is true
                set appName to name of frontProc
                set windowTitle to ""
                try
                    if (count of windows of frontProc) > 0 then
                        set windowTitle to name of front window of frontProc
                    end if
                end try
                return appName & "||" & windowTitle
            end tell
        `;

        return new Promise((resolve) => {
            execFile('osascript', ['-e', script], { timeout: 3000 }, (error, stdout) => {
                if (error) {
                    resolve({ appName: '', windowTitle: '' });
                    return;
                }

                const [appName = '', windowTitle = ''] = String(stdout || '').trim().split('||');
                resolve({
                    appName: appName.trim(),
                    windowTitle: windowTitle.trim(),
                });
            });
        });
    }

    function normalizeCaptureError(errorText) {
        if (String(errorText).includes('could not create image from display')) {
            return `${errorText}。请在 macOS 系统设置 > 隐私与安全性 > 屏幕录制 中允许当前运行 Electron 的宿主应用，然后完全重启应用。`;
        }
        return errorText;
    }

    if (typeof window !== 'undefined') {
        window.captureScreen = captureScreen;
    }

    if (typeof global !== 'undefined') {
        global.captureScreen = captureScreen;
    }

    module.exports = {
        captureScreen,
    };
})();
