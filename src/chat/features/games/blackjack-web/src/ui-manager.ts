import dialogueConfig from './dialogue.json';

// A type for the different views
export type View = 'betting-view' | 'game-view' | 'end-game-view';

export class UIManager {
    // DOM Elements
    private bettingView: HTMLElement;
    private gameView: HTMLElement;
    private endGameView: HTMLElement;
    private endGameDealerImageEl: HTMLImageElement;
    private endGameDialogueTextEl: HTMLElement;
    private endGameCountdownEl: HTMLElement;
    private continueGameButton: HTMLButtonElement;
    private quitGameButton: HTMLButtonElement;
    private messagesEl: HTMLElement;
    private gameMessagesEl: HTMLElement;

    // Dealer elements for each view
    private bettingDealerImage: HTMLImageElement;
    private bettingDialogueText: HTMLElement;
    private gameDealerImage: HTMLImageElement;
    private dialogueTextElements: HTMLElement[];
    private bettingDialogueBox: HTMLElement;
    private gameDialogueBox: HTMLElement;
    private endGameDialogueBox: HTMLElement;

    // State
    private dialogueQueue: { message: string; callback?: () => void }[] = [];
    private isSpeaking: boolean = false;

    constructor() {
        // Query all elements on construction
        this.bettingView = document.getElementById('betting-view')!;
        this.gameView = document.getElementById('game-view')!;
        this.endGameView = document.getElementById('end-game-view')!;
        this.endGameDealerImageEl = document.getElementById('end-game-dealer-image') as HTMLImageElement;
        this.endGameDialogueTextEl = document.getElementById('end-game-dialogue-text')!;
        this.endGameCountdownEl = document.getElementById('end-game-countdown')!;
        this.continueGameButton = document.getElementById('continue-game-button') as HTMLButtonElement;
        this.quitGameButton = document.getElementById('quit-game-button') as HTMLButtonElement;
        this.messagesEl = document.getElementById('messages')!;
        this.gameMessagesEl = document.getElementById('game-messages')!;

        // Betting view dealer
        this.bettingDealerImage = document.getElementById('betting-dealer-image') as HTMLImageElement;
        this.bettingDialogueText = document.getElementById('betting-dealer-dialogue-text')!;
        this.bettingDialogueBox = document.getElementById('betting-dealer-dialogue-box')!;

        // Game view dealer
        this.gameDealerImage = document.getElementById('game-dealer-image') as HTMLImageElement;
        this.dialogueTextElements = [
            this.bettingDialogueText,
            document.getElementById('game-dealer-dialogue-text')!,
            this.endGameDialogueTextEl
        ];
        this.gameDialogueBox = document.getElementById('game-dealer-dialogue-box')!;

        // End game view dealer
        this.endGameDialogueBox = document.getElementById('end-game-dialogue-box')!;
    }

    public showView(viewId: View) {
        this.bettingView.classList.add('hidden');
        this.gameView.classList.add('hidden');
        this.endGameView.classList.add('hidden');

        const viewToShow = document.getElementById(viewId);
        if (viewToShow) {
            viewToShow.classList.remove('hidden');
        }

    }

    public updateMessages(message: string, isDialogue: boolean = false, onDialogueComplete?: () => void) {
        if (isDialogue) {
            this.dialogueQueue.push({ message, callback: onDialogueComplete });
            if (!this.isSpeaking) {
                this.processDialogueQueue();
            }
        } else {
            this.messagesEl.textContent = message;
            this.gameMessagesEl.textContent = message;
        }
    }

    public showDialogue(category: string, replacements?: Record<string, string>) {
        const dialogues = (dialogueConfig as any)[category] as string[];
        if (!dialogues) return;

        let dialogueTemplate = dialogues[Math.floor(Math.random() * dialogues.length)];

        if (replacements) {
            for (const key in replacements) {
                dialogueTemplate = dialogueTemplate.replace(new RegExp(`\\$\\{${key}\\}`, 'g'), replacements[key]);
            }
        }
        this.updateMessages(dialogueTemplate, true);
    }

    private typewriterEffect(text: string, speed: number = 50, callback?: () => void) {
        this.dialogueTextElements.forEach(el => el.textContent = '');
        let i = 0;
        const interval = setInterval(() => {
            if (i < text.length) {
                const char = text.charAt(i);
                this.dialogueTextElements.forEach(el => el.textContent += char);
                i++;
            } else {
                clearInterval(interval);
                if (callback) {
                    callback();
                }
            }
        }, speed);
    }

    private processDialogueQueue() {
        if (this.dialogueQueue.length === 0) {
            this.isSpeaking = false;
            // Optionally hide dialogue box after a delay
            // setTimeout(() => this.dialogueBoxEl.style.display = 'none', 2000);
            return;
        }

        this.isSpeaking = true;
        const dialogueItem = this.dialogueQueue.shift();
        if (dialogueItem) {
            this.bettingDialogueBox.style.display = 'block';
            this.gameDialogueBox.style.display = 'block';
            this.typewriterEffect(dialogueItem.message, 40, () => {
                if (dialogueItem.callback) {
                    dialogueItem.callback();
                }
                setTimeout(() => this.processDialogueQueue(), 1000);
            });
        }
    }

    public updateDealerExpression(
        gameResult: 'win' | 'loss' | 'push' | 'blackjack',
        currentBet: number,
        totalBalance: number,
        onDialogueComplete?: () => void
    ) {
        let dialogueKey: 'win' | 'loss' | 'push' | 'blackjack';

        if (gameResult === 'win') {
            dialogueKey = 'loss'; // Player wins, so dealer loses
        } else if (gameResult === 'loss') {
            dialogueKey = 'win'; // Player loses, so dealer wins
        } else {
            dialogueKey = gameResult;
        }

        let betCategory: 'low_bet' | 'medium_bet' | 'high_bet' | 'any_bet';
        const betRatio = totalBalance > 0 ? currentBet / totalBalance : 0;

        if (dialogueKey === 'push' || dialogueKey === 'blackjack') {
            betCategory = 'any_bet';
        } else {
            if (betRatio < 0.1) { // Less than 10% is a low bet
                betCategory = 'low_bet';
            } else if (betRatio >= 0.25) { // 25% or more is a high bet
                betCategory = 'high_bet';
            } else {
                betCategory = 'medium_bet';
            }
        }

        const dialogues = (dialogueConfig as any)[dialogueKey][betCategory] as string[];
        const randomDialogueTemplate = dialogues[Math.floor(Math.random() * dialogues.length)];
        const randomDialogue = randomDialogueTemplate.replace(/\${amount}/g, currentBet.toString());

        let newImageSrc = '';
        if (gameResult === 'win' || gameResult === 'blackjack') {
            newImageSrc = '/character/lose.png';
        } else if (gameResult === 'loss') {
            newImageSrc = '/character/win.png';
        } else {
            newImageSrc = '/character/normal.png';
        }

        // Ensure image is updated before showing dialogue
        let dialogueShown = false;

        const dealerImageToUpdate = this.gameDealerImage;

        dealerImageToUpdate.onload = () => {
            if (!dialogueShown) {
                dialogueShown = true;
                this.gameDialogueBox.style.display = 'block';
                this.updateMessages(randomDialogue, true, onDialogueComplete);
            }
        };
        dealerImageToUpdate.src = newImageSrc;
        if (dealerImageToUpdate.complete && !dialogueShown) {
            dialogueShown = true;
            this.gameDialogueBox.style.display = 'block';
            this.updateMessages(randomDialogue, true, onDialogueComplete);
        }
    }


    public showBetPlacedDialogue(
        betAmount: number,
        totalBalance: number,
        isAllIn: boolean
    ) {
        let betCategory: 'low_bet' | 'medium_bet' | 'high_bet' | 'all_in';
        const betRatio = totalBalance > 0 ? betAmount / totalBalance : 0;

        if (isAllIn) {
            betCategory = 'all_in';
        } else if (betRatio < 0.1) { // Less than 10% is a low bet
            betCategory = 'low_bet';
        } else if (betRatio >= 0.25) { // 25% or more is a high bet
            betCategory = 'high_bet';
        } else {
            betCategory = 'medium_bet';
        }

        const betDialogues = (dialogueConfig as any).bet_placed[betCategory] as string[];
        const randomDialogueTemplate = betDialogues[Math.floor(Math.random() * betDialogues.length)];
        const randomDialogue = randomDialogueTemplate.replace(/\${amount}/g, betAmount.toString());
        this.bettingDealerImage.src = '/character/normal.png';
        this.bettingDialogueBox.style.display = 'block';
        this.updateMessages(randomDialogue, true);
    }

    public resetDealer() {
        this.bettingDealerImage.src = '/character/normal.png';
        this.gameDealerImage.src = '/character/normal.png';
        this.bettingDialogueBox.style.display = 'none';
        this.gameDialogueBox.style.display = 'none';
    }
    public showEndGameView(
        gameResult: 'win' | 'loss' | 'push' | 'blackjack',
        countdownCallback: () => void
    ): { countdownInterval: number } {
        this.showView('end-game-view');

        let dialogueCategory: string;
        let buttonTexts: { continue: string; quit: string };
        let dealerImage: string;

        if (gameResult === 'win' || gameResult === 'blackjack') {
            dialogueCategory = 'end_game_win';
            buttonTexts = { continue: "乘胜追击", quit: "见好就收" };
            dealerImage = '/character/lose.png';
        } else if (gameResult === 'loss') {
            dialogueCategory = 'end_game_loss';
            buttonTexts = { continue: "扳回一局", quit: "愿赌服输" };
            dealerImage = '/character/win.png';
        } else { // push
            dialogueCategory = 'end_game_push';
            buttonTexts = { continue: "再来一局", quit: "不玩了" };
            dealerImage = '/character/normal.png';
        }

        this.continueGameButton.textContent = buttonTexts.continue;
        this.quitGameButton.textContent = buttonTexts.quit;
        this.endGameDealerImageEl.src = dealerImage;

        const dialogues = (dialogueConfig as any)[dialogueCategory] as string[];
        // --- New Dialogue Cycling Logic ---
        // 1. Shuffle the dialogues array to ensure random order
        const shuffledDialogues = [...dialogues].sort(() => 0.5 - Math.random());
        let dialogueIndex = 0;

        // 2. Display the first dialogue immediately
        this.updateMessages(shuffledDialogues[dialogueIndex], true);
        this.endGameDialogueBox.style.display = 'block';

        let seconds = 10; // 恢复为10秒倒计时
        this.endGameCountdownEl.textContent = seconds.toString();
        this.endGameCountdownEl.classList.remove('warning'); // 重置颜色

        const dialogueInterval = setInterval(() => {
            dialogueIndex = (dialogueIndex + 1) % shuffledDialogues.length;
            this.updateMessages(shuffledDialogues[dialogueIndex], true);
        }, 3500);

        // Observer to clear interval when view is hidden
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.attributeName === 'class') {
                    const targetNode = mutation.target as HTMLElement;
                    if (targetNode.classList.contains('hidden')) {
                        clearInterval(dialogueInterval);
                        observer.disconnect();
                        break;
                    }
                }
            }
        });
        observer.observe(this.endGameView, { attributes: true });

        const countdownInterval = setInterval(() => {
            // 先更新数字和颜色
            this.endGameCountdownEl.textContent = seconds.toString();
            if (seconds <= 3) {
                this.endGameCountdownEl.classList.add('warning');
            }

            // 再执行震动
            // 1. 移除所有旧的震动class
            this.endGameView.classList.remove('shake', 'shake-light', 'shake-medium', 'shake-strong');

            // 2. 根据剩余时间决定震动强度
            let shakeClass = '';
            if (seconds > 6) {
                shakeClass = 'shake-light';
            } else if (seconds > 3) {
                shakeClass = 'shake-medium';
            } else {
                shakeClass = 'shake-strong';
            }

            // 3. 应用新的震动class
            this.endGameView.classList.add(shakeClass);

            // 4. 动画结束后移除class
            setTimeout(() => {
                this.endGameView.classList.remove(shakeClass);
            }, 400); // 动画时长为0.4s

            // 最后检查是否结束
            if (seconds <= 0) {
                clearInterval(countdownInterval);
                clearInterval(dialogueInterval);
                observer.disconnect();
                countdownCallback();
            }

            seconds--;
        }, 1000);

        return { countdownInterval };
    }
}