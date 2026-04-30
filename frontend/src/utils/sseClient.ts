export interface SSEMessage {
  type: 'progress' | 'chunk' | 'result' | 'error' | 'done' | 'start' | 'content';
  message?: string;
  progress?: number;
  word_count?: number;
  status?: 'processing' | 'success' | 'error' | 'warning';
  content?: string;
  data?: unknown;
  error?: string;
  code?: number;
}

export interface SSEClientOptions<TResult = unknown> {
  onProgress?: (message: string, progress: number, status: string, wordCount?: number) => void;
  onChunk?: (content: string) => void;
  onResult?: (data: TResult) => void;
  onError?: (error: string, code?: number) => void;
  onComplete?: () => void;
  onConnectionError?: (error: Event) => void;
  signal?: AbortSignal;
}

type ResolveSSE = (value: unknown) => void;
type RejectSSE = (reason?: unknown) => void;

export class SSEClient<TResult = unknown> {
  private eventSource: EventSource | null = null;
  private url: string;
  private options: SSEClientOptions<TResult>;
  private accumulatedContent = '';
  private resultData: TResult | undefined;

  constructor(url: string, options: SSEClientOptions<TResult> = {}) {
    this.url = url;
    this.options = options;
  }

  connect(): Promise<unknown> {
    return new Promise((resolve, reject) => {
      try {
        this.eventSource = new EventSource(this.url);

        this.eventSource.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as SSEMessage;
            this.handleMessage(message, resolve, reject);
          } catch (error) {
            console.error('解析SSE消息失败:', error);
          }
        };

        this.eventSource.onerror = (error) => {
          console.error('SSE连接错误:', error);
          this.options.onConnectionError?.(error);
          this.close();
          reject(new Error('SSE连接失败'));
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  private handleMessage(message: SSEMessage, resolve: ResolveSSE, reject: RejectSSE) {
    switch (message.type) {
      case 'progress':
        if (this.options.onProgress && message.progress !== undefined) {
          this.options.onProgress(
            message.message || '',
            message.progress,
            message.status || 'processing',
            message.word_count
          );
        }
        break;

      case 'chunk':
      case 'content':
        if (message.content) {
          this.accumulatedContent += message.content;
          this.options.onChunk?.(message.content);
        }
        break;

      case 'result':
        if (message.data !== undefined) {
          this.resultData = message.data as TResult;
          this.options.onResult?.(this.resultData);
        }
        break;

      case 'error':
        this.options.onError?.(message.error || '未知错误', message.code);
        this.close();
        reject(new Error(message.error || '未知错误'));
        break;

      case 'done':
        this.options.onComplete?.();
        this.close();
        if (this.resultData !== undefined) {
          resolve(this.resultData);
        } else {
          resolve(this.accumulatedContent ? { content: this.accumulatedContent } : true);
        }
        break;

      case 'start':
        console.debug(`[SSE] 收到消息类型: ${message.type}`, message);
        break;

      default:
        console.debug(`[SSE] 收到未处理的消息类型: ${message.type}`, message);
        break;
    }
  }

  close() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  getAccumulatedContent(): string {
    return this.accumulatedContent;
  }
}

export class SSEPostClient<TResult = unknown, TRequest = unknown> {
  private url: string;
  private data: TRequest;
  private options: SSEClientOptions<TResult>;
  private abortController: AbortController | null = null;
  private accumulatedContent = '';
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private isAborted = false;
  private resultData: TResult | undefined;

  constructor(url: string, data: TRequest, options: SSEClientOptions<TResult> = {}) {
    this.url = url;
    this.data = data;
    this.options = options;
  }

  connect(): Promise<unknown> {
    return new Promise((resolve, reject) => {
      void this.connectStream(resolve, reject);
    });
  }

  private async connectStream(resolve: ResolveSSE, reject: RejectSSE): Promise<void> {
    const externalSignal = this.options.signal;
    const abortHandler = () => this.abort();

    try {
      this.abortController = new AbortController();
      this.isAborted = false;

      if (externalSignal?.aborted) {
        this.abort();
        reject(new DOMException('Request aborted', 'AbortError'));
        return;
      }

      externalSignal?.addEventListener('abort', abortHandler, { once: true });

      const response = await fetch(this.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(this.data),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      this.reader = response.body?.getReader() || null;
      const decoder = new TextDecoder();

      if (!this.reader) {
        throw new Error('无法获取响应流');
      }

      let buffer = '';

      while (!this.isAborted) {
        const { done, value } = await this.reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim() === '' || line.startsWith(':')) {
            continue;
          }

          try {
            const dataMatch = line.match(/^data: (.+)$/m);
            if (dataMatch) {
              const message = JSON.parse(dataMatch[1]) as SSEMessage;
              this.handleMessage(message, resolve, reject);
            }
          } catch (error) {
            console.error('解析SSE消息失败:', error, line);
          }
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        console.log('Request aborted');
        reject(error);
      } else {
        const message = error instanceof Error ? error.message : 'Request failed';
        console.error('SSE POST request failed:', error);
        this.options.onError?.(message);
        reject(error);
      }
    } finally {
      externalSignal?.removeEventListener('abort', abortHandler);
      await this.closeReader();
    }
  }

  private async closeReader(): Promise<void> {
    if (this.reader) {
      try {
        await this.reader.cancel();
      } catch (error) {
        console.debug('关闭 reader 时出错:', error);
      }
      this.reader = null;
    }
  }

  private handleMessage(message: SSEMessage, resolve: ResolveSSE, reject: RejectSSE) {
    switch (message.type) {
      case 'progress':
        if (this.options.onProgress && message.progress !== undefined) {
          this.options.onProgress(
            message.message || '',
            message.progress,
            message.status || 'processing',
            message.word_count
          );
        }
        break;

      case 'chunk':
      case 'content':
        if (message.content) {
          this.accumulatedContent += message.content;
          this.options.onChunk?.(message.content);
        }
        break;

      case 'result':
        if (message.data !== undefined) {
          this.resultData = message.data as TResult;
          this.options.onResult?.(this.resultData);
        }
        break;

      case 'error':
        this.options.onError?.(message.error || '未知错误', message.code);
        reject(new Error(message.error || '未知错误'));
        break;

      case 'done':
        this.options.onComplete?.();
        if (this.resultData !== undefined) {
          resolve(this.resultData);
        } else if (this.accumulatedContent) {
          resolve({ content: this.accumulatedContent });
        } else {
          resolve(true);
        }
        break;

      case 'start':
        console.debug(`[SSE] 收到消息类型: ${message.type}`, message);
        break;

      default:
        console.debug(`[SSE] 收到未处理的消息类型: ${message.type}`, message);
        break;
    }
  }

  abort() {
    this.isAborted = true;
    if (this.abortController) {
      this.abortController.abort();
    }
    if (this.reader) {
      this.reader.cancel().catch((error) => {
        console.debug('取消 reader 失败:', error);
      });
      this.reader = null;
    }
  }

  getAccumulatedContent(): string {
    return this.accumulatedContent;
  }
}

export async function ssePost<TResult = unknown, TRequest = unknown>(
  url: string,
  data: TRequest,
  options: SSEClientOptions<TResult> = {}
): Promise<TResult> {
  const client = new SSEPostClient<TResult, TRequest>(url, data, options);
  try {
    return await client.connect() as TResult;
  } finally {
    client.abort();
  }
}
