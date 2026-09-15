import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/contexts/AuthContext';
import { useLocation } from 'wouter';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useBranding } from '@/contexts/BrandingContext';
import { Spinner } from '@/components/ui/spinner';
import { setMfaChallengeToken } from '@/lib/api';

/**
 * Login Page
 * 
 * Design: Professional medical SaaS login
 * - Centered card layout
 * - Logo from branding
 * - Identifiant + mot de passe form
 * - MFA flow : si le login retourne un challenge_token, redirige vers /mfa-verify
 * - Rate limiting awareness (429 handling)
 * - Error messages from backend
 */
export default function Login() {
  const { login, isLoading } = useAuth();
  const [, setLocation] = useLocation();
  const { branding } = useBranding();
  const { t } = useTranslation();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const result = await login(identifier, password);
      if (result.requiresMfa) {
        if (result.challengeToken) {
          setMfaChallengeToken(result.challengeToken);
        }
        setLocation('/mfa-verify');
      } else {
        setLocation(result.user?.role === 'super_admin' ? '/super-admin' : '/dashboard');
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      let message = t('auth.loginError');
      if (err.response?.status === 429) {
        message = t('auth.tooManyAttempts');
      } else if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.map((item: any) => (typeof item === 'string' ? item : item?.msg || JSON.stringify(item))).join(', ');
      } else if (detail && typeof detail === 'object') {
        message = JSON.stringify(detail);
      }
      setError(message);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="space-y-4 text-center">
          {branding?.logo_url && (
            <img
              src={branding.logo_url}
              alt={t('auth.logoAlt')}
              className="h-16 w-16 mx-auto object-contain"
            />
          )}
          <div>
            <CardTitle className="text-2xl">{branding?.nom_clinique || t('auth.clinic')}</CardTitle>
            <CardDescription>{t('auth.loginSubtitle')}</CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="identifier">{t('auth.identifier')}</Label>
              <Input
                id="identifier"
                type="text"
                autoComplete="username"
                placeholder={t('auth.identifierPlaceholder')}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">{t('auth.password')}</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                required
              />
            </div>

            {error && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  {t('auth.loggingIn')}
                </>
              ) : (
                t('auth.loginButton')
              )}
            </Button>
          </form>

          <p className="text-xs text-muted-foreground text-center mt-4">
            {t('auth.securityFooter')}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
