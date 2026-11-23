"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signIn } from "next-auth/react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2, ShieldCheck, Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

const registerSchema = z
  .object({
    full_name: z.string().min(2, "Full name must be at least 2 characters"),
    email: z.string().email("Enter a valid email"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/[A-Za-z]/, "Must contain at least one letter")
      .regex(/\d/, "Must contain at least one number"),
    confirm_password: z.string(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RegisterForm = z.infer<typeof registerSchema>;

function PasswordInput({
  id,
  label,
  placeholder,
  autocomplete,
  error,
  registration,
}: {
  id: string;
  label: string;
  placeholder: string;
  autocomplete: string;
  error?: string;
  registration: object;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <div className="relative mt-1">
        <input
          id={id}
          type={show ? "text" : "password"}
          autoComplete={autocomplete}
          {...registration}
          className={cn(
            "block w-full rounded-lg border px-3 py-2 pr-10 text-sm shadow-sm",
            "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
            error ? "border-red-400 bg-red-50" : "border-gray-300 bg-white"
          )}
          placeholder={placeholder}
        />
        <button
          type="button"
          onClick={() => setShow((v) => !v)}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600"
          tabIndex={-1}
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}

export default function RegisterPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });

  async function onSubmit(data: RegisterForm) {
    setIsLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/register`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: data.email,
            password: data.password,
            full_name: data.full_name,
          }),
        }
      );

      if (res.status === 409) {
        toast.error("Email already registered. Please sign in.");
        return;
      }
      if (!res.ok) {
        const err = await res.json();
        toast.error(err.detail ?? "Registration failed");
        return;
      }

      const signInResult = await signIn("credentials", {
        email: data.email,
        password: data.password,
        redirect: false,
      });

      if (signInResult?.error) {
        toast.success("Account created! Please sign in.");
        router.push("/login");
        return;
      }

      toast.success("Welcome to SafeSite!");
      router.push("/dashboard");
      router.refresh();
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-12">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="flex justify-center">
            <div className="rounded-xl bg-blue-600 p-3">
              <ShieldCheck className="h-8 w-8 text-white" />
            </div>
          </div>
          <h1 className="mt-4 text-2xl font-bold tracking-tight text-gray-900">
            Create your account
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Start monitoring your construction sites today
          </p>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-5 rounded-2xl border border-gray-200 bg-white p-8 shadow-sm"
        >
          {/* Full name */}
          <div>
            <label htmlFor="full_name" className="block text-sm font-medium text-gray-700">
              Full name
            </label>
            <input
              id="full_name"
              type="text"
              autoComplete="name"
              {...register("full_name")}
              className={cn(
                "mt-1 block w-full rounded-lg border px-3 py-2 text-sm shadow-sm",
                "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
                errors.full_name ? "border-red-400 bg-red-50" : "border-gray-300 bg-white"
              )}
              placeholder="Alex Johnson"
            />
            {errors.full_name && (
              <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>
            )}
          </div>

          {/* Email */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Email address
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              {...register("email")}
              className={cn(
                "mt-1 block w-full rounded-lg border px-3 py-2 text-sm shadow-sm",
                "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
                errors.email ? "border-red-400 bg-red-50" : "border-gray-300 bg-white"
              )}
              placeholder="you@company.com"
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
            )}
          </div>

          {/* Password */}
          <PasswordInput
            id="password"
            label="Password"
            placeholder="Min 8 chars, 1 letter, 1 number"
            autocomplete="new-password"
            error={errors.password?.message}
            registration={register("password")}
          />

          {/* Confirm password */}
          <PasswordInput
            id="confirm_password"
            label="Confirm password"
            placeholder="Repeat password"
            autocomplete="new-password"
            error={errors.confirm_password?.message}
            registration={register("confirm_password")}
          />

          <button
            type="submit"
            disabled={isLoading}
            className={cn(
              "flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5",
              "bg-blue-600 text-sm font-semibold text-white",
              "hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
              "disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            )}
          >
            {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
            Create account
          </button>

          <p className="text-center text-sm text-gray-500">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-blue-600 hover:text-blue-500">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}