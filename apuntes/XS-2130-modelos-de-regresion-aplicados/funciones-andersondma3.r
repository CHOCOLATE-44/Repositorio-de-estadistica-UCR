sim.beta=function(a,b,sig,n){
  x=runif(n,1,10)
  y=a+b*x+rnorm(n,0,sig)  
  return(list("x"=x,"y"=y))
}

simul1=function(a,b,sig,n,nrep,t=1){
  x11()
  par(mfrow=c(2,2))
  for(j in 1:4){
    s1=sim.beta(a,b,sig,n)
    X=s1$x;Y=s1$y
    z=qnorm(0.975)
    plot(X,Y,type="n",xlim=c(0,10),ylim=c(a-z*sig,a+b*10+z*sig))
    w=ifelse(j==1,2,0.5)
    Sys.sleep(w)
    abline(a,b,col=2)
    Sys.sleep(w)
    mod=lm(s1$y~s1$x) 
    for(i in 1:n){
      r1=X[i];r2=a+b*r1
      segments(r1,r2+z*sig,r1,r2-z*sig,lty=2)
      w=ifelse(j==1,t,t/4)
      Sys.sleep(w)
      points(s1$x[i],s1$y[i],pch=18,col=4)
      Sys.sleep(w)
    }
    abline(mod,col=4,lty=2)
    Sys.sleep(2)
  }
  #summary(mod) 
}

simul2=function(a,b,sig,n,nrep,t=1){
  x11()
  layout(matrix(c(1,1,2,3),2,2),widths = c(2,1))
  plot(0,0,xlim=c(0,10),ylim=c(0,70),xlab="x",ylab="y",type="n")
  text(0,70,bquote(n == .(n)),pos=4)
  text(0,68,bquote(sigma == .(sig)),pos=4)
  abline(a,b,col=2,lwd=2)
                                            
  beta=matrix(nrow=nrep,ncol=2)
  for(i in 1:nrep){
    s1=sim.beta(a,b,sig,n)
    abline(lm(s1$y~s1$x),col="blue")
    beta[i,]=lm(s1$y~s1$x)$coef
    Sys.sleep(t)
  }
  plot(density(beta[,1]),main="Intersecciones",xlab=expression(hat(beta)[0]),
       xlim=c(a/4,1.75*a),ylab="")
  abline(v=a,col=2)
  plot(density(beta[,2]),main="Pendientes",xlab=expression(hat(beta)[1]),
       xlim=c(b/4,1.55*b),ylab="")
  abline(v=b,col=2)
}



##################


