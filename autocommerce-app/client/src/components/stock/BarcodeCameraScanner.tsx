import { useTranslation } from 'react-i18next';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { BrowserMultiFormatReader, IScannerControls } from '@zxing/browser';
import { BarcodeFormat, DecodeHintType, NotFoundException } from '@zxing/library';
import { Button } from '@/components/ui/button';
import { AlertCircle, Camera, CameraOff, Check, PackagePlus, RotateCcw, X } from 'lucide-react';

interface BarcodeCameraScannerProps {
  /** Appelé avec le texte décodé après validation explicite de l'utilisateur. */
  onDetected: (code: string) => void;
  /** Appelé avec le code décodé pour déclencher une réception / ajout de stock. */
  onReceptionDetected?: (code: string) => void;
  /** Format d'affichage : plein cadre ou compact. */
  compact?: boolean;
}

/**
 * Scanner caméra réel — QR code et codes-barres (Code 128, EAN, UPC...).
 *
 * Corrections apportées :
 *  - boucle de décodage continue via `decodeFromVideoDevice` (fiable sur
 *    Android/iOS), au lieu de `decodeFromConstraints` qui ne tournait pas
 *    sur certains téléphones ;
 *  - formats restreints pour une détection plus rapide ;
 *  - repli automatique sur la caméra arrière ;
 *  - panneau « Code détecté » avec boutons explicites : {t('componentUi.validateScan')},
 *    {t('componentUi.scanAgain')}, {t('componentUi.cancel')}.
 *
 * Le résultat est présenté à l'utilisateur avant transmission au flux stock.
 */
export function BarcodeCameraScanner({
  onDetected, onReceptionDetected, compact = false }: BarcodeCameraScannerProps) {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const readerRef = useRef<BrowserMultiFormatReader | null>(null);
  const deviceIdRef = useRef<string | undefined>(undefined);
  const lastCodeRef = useRef<{ code: string; at: number } | null>(null);
  const nativeScanTimerRef = useRef<number | null>(null);
  const nativeScanBusyRef = useRef(false);

  const [isActive, setIsActive] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingCode, setPendingCode] = useState<string | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState<string | undefined>(undefined);

  useEffect(() => {
    return () => {
      controlsRef.current?.stop();
      controlsRef.current = null;
      if (nativeScanTimerRef.current !== null) {
        window.clearInterval(nativeScanTimerRef.current);
        nativeScanTimerRef.current = null;
      }
    };
  }, []);

  const selectDevice = useCallback((id: string | undefined) => {
    deviceIdRef.current = id;
    setDeviceId(id);
  }, []);

  const listCameras = useCallback(async () => {
    try {
      const cams = await BrowserMultiFormatReader.listVideoInputDevices();
      setDevices(cams);
      const back = cams.find((d) => /back|rear|environment/i.test(d.label));
      selectDevice((back || cams[cams.length - 1])?.deviceId);
    } catch {
      // Certains navigateurs masquent les appareils avant l'autorisation caméra.
    }
  }, [selectDevice]);

  useEffect(() => {
    void listCameras();
  }, [listCameras]);

  const getReader = useCallback(() => {
    if (!readerRef.current) {
      const hints = new Map<DecodeHintType, unknown>();
      hints.set(DecodeHintType.POSSIBLE_FORMATS, [
        BarcodeFormat.QR_CODE,
        BarcodeFormat.CODE_128,
        BarcodeFormat.CODE_39,
        BarcodeFormat.CODE_93,
        BarcodeFormat.EAN_13,
        BarcodeFormat.EAN_8,
        BarcodeFormat.UPC_A,
        BarcodeFormat.UPC_E,
        BarcodeFormat.ITF,
        BarcodeFormat.DATA_MATRIX,
        BarcodeFormat.AZTEC,
        BarcodeFormat.PDF_417,
      ]);
      readerRef.current = new BrowserMultiFormatReader(hints);
    }
    return readerRef.current;
  }, []);

  const publishDetectedCode = useCallback((rawCode: string) => {
    const code = rawCode.trim();
    const now = Date.now();
    if (!code || (lastCodeRef.current?.code === code && now - lastCodeRef.current.at < 3000)) return;
    lastCodeRef.current = { code, at: now };
    controlsRef.current?.stop();
    controlsRef.current = null;
    if (nativeScanTimerRef.current !== null) {
      window.clearInterval(nativeScanTimerRef.current);
      nativeScanTimerRef.current = null;
    }
    setIsActive(false);
    setPendingCode(code);
  }, []);

  const startNativeFallback = useCallback((videoEl: HTMLVideoElement) => {
    const Detector = (window as Window & { BarcodeDetector?: any }).BarcodeDetector;
    if (!Detector || nativeScanTimerRef.current !== null) return;

    let detector: any;
    try {
      detector = new Detector({
        formats: ['qr_code', 'code_128', 'code_39', 'code_93', 'ean_13', 'ean_8', 'upc_a', 'upc_e', 'itf', 'data_matrix', 'aztec', 'pdf417'],
      });
    } catch {
      try { detector = new Detector(); } catch { return; }
    }

    nativeScanTimerRef.current = window.setInterval(() => {
      if (nativeScanBusyRef.current || videoEl.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !videoEl.videoWidth) return;
      nativeScanBusyRef.current = true;
      void detector.detect(videoEl)
        .then((items: Array<{ rawValue?: string }>) => {
          const value = items?.find((item) => item.rawValue?.trim())?.rawValue;
          if (value) publishDetectedCode(value);
        })
        .catch(() => undefined)
        .finally(() => { nativeScanBusyRef.current = false; });
    }, 300);
  }, [publishDetectedCode]);

  const start = useCallback(async () => {
    setError(null);
    setPendingCode(null);
    setIsStarting(true);
    const videoEl = videoRef.current;
    if (!videoEl) return;

    try {
      const reader = getReader();
      const controls = await reader.decodeFromVideoDevice(
        deviceIdRef.current,
        videoEl,
        (result, err) => {
          if (result) {
            publishDetectedCode(result.getText());
          } else if (err && !(err instanceof NotFoundException)) {
            console.error('Erreur de scan caméra:', err);
          }
        },
      );
      controlsRef.current = controls;
      setIsActive(true);

      // Certains navigateurs mobiles ne lancent pas la lecture vidéo tout de
      // suite après l'autorisation : on la force (plusieurs tentatives).
      const ensurePlay = async () => {
        try {
          await videoEl.play();
        } catch {
          /* déjà en lecture ou autoplay bloqué — ZXing gère le flux */
        }
      };
      void ensurePlay();
      window.setTimeout(() => void ensurePlay(), 500);
      window.setTimeout(() => void ensurePlay(), 1200);
      startNativeFallback(videoEl);

      await listCameras().catch(() => undefined);
    } catch (e: any) {
      let message = t('componentUi.cameraAccess');
      if (e?.name === 'NotAllowedError') {
        message = t('componentUi.cameraDenied');
      } else if (e?.name === 'NotFoundError') {
        message = t('componentUi.noCamera');
      } else if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
        message = t('componentUi.httpsRequired');
      }
      setError(message);
      setIsActive(false);
    } finally {
      setIsStarting(false);
    }
  }, [getReader, listCameras, publishDetectedCode, startNativeFallback, t]);

  const stop = useCallback(() => {
    controlsRef.current?.stop();
    controlsRef.current = null;
    if (nativeScanTimerRef.current !== null) {
      window.clearInterval(nativeScanTimerRef.current);
      nativeScanTimerRef.current = null;
    }
    setIsActive(false);
  }, []);

  const validateDetectedCode = () => {
    if (!pendingCode) return;
    const code = pendingCode;
    setPendingCode(null);
    onDetected(code);
  };

  const validateReceptionCode = () => {
    if (!pendingCode) return;
    const code = pendingCode;
    setPendingCode(null);
    onReceptionDetected?.(code);
  };

  const rescan = () => {
    setPendingCode(null);
    void start();
  };

  const toggle = () => {
    if (isActive) stop();
    else void start();
  };

  const switchDevice = (next: string) => {
    selectDevice(next);
    if (isActive) {
      stop();
      // Redémarre sur la caméra sélectionnée une fois l'état mis à jour.
      window.setTimeout(() => void start(), 120);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant={isActive ? 'destructive' : 'default'}
          onClick={toggle}
          disabled={isStarting}
        >
          {isActive ? <CameraOff className="w-4 h-4 mr-2" /> : <Camera className="w-4 h-4 mr-2" />}
          {isStarting ? t('componentUi.starting') : isActive ? t('componentUi.stopCamera') : t('componentUi.scanCamera')}
        </Button>
        {devices.length > 1 && isActive && (
          <select
            value={deviceId}
            onChange={(e) => switchDevice(e.target.value)}
            aria-label={t('componentUi.cameraSelection')}
            className="h-9 px-3 border rounded-md text-sm bg-background"
          >
            {devices.map((d, index) => (
              <option key={d.deviceId} value={d.deviceId}>{d.label || t('componentUi.cameraNumber', { number: index + 1 })}</option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 rounded-md p-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {pendingCode && (
        <div className="flex flex-col gap-3 rounded-md border border-primary/40 bg-primary/5 p-3 text-sm">
          <div>
            <span className="font-medium block mb-1">{t('componentUi.detectedCode')}</span>
            <span className="font-mono text-base break-all bg-background border rounded px-2 py-1 inline-block">
              {pendingCode}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {onReceptionDetected && (
              <Button type="button" variant="secondary" onClick={validateReceptionCode}>
                <PackagePlus className="w-4 h-4 mr-1" /> {t('componentUi.addStockReception')}
              </Button>
            )}
            <Button type="button" onClick={validateDetectedCode}>
              <Check className="w-4 h-4 mr-1" /> {t('componentUi.validateScan')}
            </Button>
            <Button type="button" variant="outline" onClick={rescan}>
              <RotateCcw className="w-4 h-4 mr-1" /> {t('componentUi.scanAgain')}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setPendingCode(null)}>
              <X className="w-4 h-4 mr-1" /> {t('componentUi.cancel')}
            </Button>
          </div>
        </div>
      )}

      <div
        className={`relative overflow-hidden rounded-md bg-black ${isActive ? '' : 'hidden'} ${compact ? 'aspect-video max-h-48' : 'aspect-video'}`}
      >
        <video ref={videoRef} className="w-full h-full object-cover" aria-label={t('componentUi.scannerVideo')} muted playsInline />
        {isActive && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-2/3 h-2/3 border-2 border-white/70 rounded-lg" />
          </div>
        )}
      </div>
      {!isActive && !pendingCode && !error && (
        <p className="text-xs text-muted-foreground">
          {t('componentUi.pointCamera')}
        </p>
      )}
    </div>
  );
}

export default BarcodeCameraScanner;
